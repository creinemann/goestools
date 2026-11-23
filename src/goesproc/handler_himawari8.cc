#include "handler_himawari8.h"

#include <util/error.h>
#include <util/string.h>

#include "lib/timer.h"

#include "filename.h"
#include "string.h"

#ifdef HAS_PROJ
#include "map_drawer.h"
#endif

using namespace util;

namespace {

// Allow Himawari band names in the config as aliases for the short
// channel names goesproc uses for the HRIT relay.
std::string normalizeChannel(const std::string& in) {
  const auto s = toUpper(in);
  if (s == "B03" || s == "VIS") {
    return "VS";
  }
  if (s == "B13") {
    return "IR";
  }
  if (s == "B08") {
    return "WV";
  }
  return s;
}

} // namespace

Himawari8ImageHandler::Himawari8ImageHandler(
  const Config::Handler& config,
  const std::shared_ptr<FileWriter>& fileWriter)
  : config_(config),
    fileWriter_(fileWriter) {
  for (auto& region : config_.regions) {
    region = toUpper(region);
  }
  for (auto& channel : config_.channels) {
    channel = normalizeChannel(channel);
  }

  // Remap tables are keyed by upper-cased channel name in the config;
  // normalize aliases (e.g. [handler.remap.b03]) as well.
  std::map<std::string, cv::Mat> remap;
  for (const auto& it : config_.remap) {
    remap[normalizeChannel(it.first)] = it.second;
  }
  config_.remap = std::move(remap);
}

bool Himawari8ImageHandler::matchChannel(const Channel& channel) const {
  if (config_.channels.empty()) {
    return true;
  }
  const auto begin = std::begin(config_.channels);
  const auto end = std::end(config_.channels);
  return std::find(begin, end, channel.nameShort) != end;
}

void Himawari8ImageHandler::handle(std::shared_ptr<const lrit::File> f) {
  auto ph = f->getHeader<lrit::PrimaryHeader>();
  if (ph.fileType != 0) {
    return;
  }

  // Filter Himawari 8/9
  auto nlh = f->getHeader<lrit::NOAALRITHeader>();
  if (nlh.productID != 43) {
    return;
  }

  // All images relayed from Himawari are segmented.
  // I have seen files without segment identification header
  // and that have fewer bytes than listed in the header.
  // I think they are corrupted, so let's ignore them.
  if (!f->hasHeader<lrit::SegmentIdentificationHeader>()) {
    return;
  }

  // Expect only full disk images
  if (nlh.productSubID % 2 != 1) {
    return;
  }
  Region region;
  region.nameShort = "FD";
  region.nameLong = "Full Disk";

  // Extract channel information
  Channel channel;
  if (nlh.productSubID == 1) {
    channel.nameShort = "VS";
    channel.nameLong = "Visible";
  } else if (nlh.productSubID == 3) {
    channel.nameShort = "IR";
    channel.nameLong = "Infrared";
  } else if (nlh.productSubID == 7) {
    channel.nameShort = "WV";
    channel.nameLong = "Water Vapor";
  } else {
    return;
  }

  if (!matchChannel(channel)) {
    return;
  }

  auto sih = f->getHeader<lrit::SegmentIdentificationHeader>();
  auto key = std::make_tuple("unused", region.nameShort, channel.nameShort);
  auto& vector = segments_[key];

  // Ensure we can append this segment
  if (!vector.empty()) {
    const auto& t = vector.front();
    if (getBasename(*t) != getBasename(*f)) {
      vector.clear();
    }
  }

  vector.push_back(f);
  if (vector.size() != sih.maxSegment) {
    return;
  }

  auto first = vector.front();
  auto image = buildImage(vector, channel);
  vector.clear();

  // False color handlers combine two channels into one image.
  if (config_.lut.data) {
    handleFalseColor(first, f, region, channel, std::move(image));
    return;
  }

  Timer t;
  FilenameBuilder fb;
  fb.dir = config_.dir;
  fb.filename = getBasename(*f);
  fb.time = getTime(*f);
  fb.region = region;
  fb.channel = channel;

  auto mat = image->getRawImage();
  overlayMaps(*f, mat);
  auto path = fb.build(config_.filename, config_.format);
  fileWriter_->write(path, mat, &t);
  if (config_.json) {
    fileWriter_->writeHeader(*first, path);
  }
}

std::unique_ptr<Image> Himawari8ImageHandler::buildImage(
    const std::vector<std::shared_ptr<const lrit::File>>& files,
    const Channel& channel) const {
  auto image = Image::createFromFiles(files);

  // Space around the disk is white (255) in the relayed IR image,
  // which a false color LUT would render as the coldest cloud tops.
  // Blank it out like the GOES-R handler does. Only done for false
  // color so plain image output stays byte-identical to before.
  if (config_.lut.data) {
    image->fillSides();
  }

  // Apply contrast curve if configured for this channel,
  // same as [handler.remap.chXX] for GOES-R.
  auto it = config_.remap.find(channel.nameShort);
  if (it != std::end(config_.remap)) {
    image->remap(it->second);
  }

  return image;
}

void Himawari8ImageHandler::handleFalseColor(
    std::shared_ptr<const lrit::File> first,
    std::shared_ptr<const lrit::File> last,
    const Region& region,
    const Channel& channel,
    std::unique_ptr<Image> image) {
  Timer t;
  const auto time = getTime(*last).tv_sec;

  // Nothing pending, or pending image is from another scan
  // (its partner never arrived): keep this one and wait.
  if (!pending_ || pending_->time != time) {
    pending_ = std::make_unique<Pending>(
      Pending{first, last, region, channel, time, std::move(image)});
    return;
  }

  // Same channel twice for the same scan: duplicate on the stream.
  if (pending_->channel.nameShort == channel.nameShort) {
    return;
  }

  // Order inputs to match the configured channel order. The first
  // channel indexes LUT rows (y), the second LUT columns (x), exactly
  // as for GOES-R (e.g. [ "ch02", "ch13" ] -> [ "vs", "ir" ]).
  auto p = std::move(pending_);
  std::unique_ptr<Image> i0;
  std::unique_ptr<Image> i1;
  if (p->channel.nameShort == config_.channels.front()) {
    i0 = std::move(p->image);
    i1 = std::move(image);
  } else {
    i0 = std::move(image);
    i1 = std::move(p->image);
  }

  // Name the synthesized image after the scan, not either input.
  // Example: IMG_DK01VIS_201712162250 -> IMG_DK01FC_201712162250
  auto basename = getBasename(*last);
  auto parts = split(basename, '_');
  if (parts.size() >= 3) {
    if (parts[1].rfind("DK", 0) == 0 && parts[1].size() >= 4) {
      parts[1] = parts[1].substr(0, 4) + "FC";
    } else {
      parts[1] += "FC";
    }
    basename = join(parts, '_');
  } else {
    basename += "_FC";
  }

  FilenameBuilder fb;
  fb.dir = config_.dir;
  fb.filename = basename;
  fb.time = getTime(*last);
  fb.region = region;
  fb.channel.nameShort = "FC";
  fb.channel.nameLong = "False Color";

  auto out = Image::generateFalseColor(i0, i1, config_.lut);
  i0.reset();
  i1.reset();

  auto mat = out->getRawImage();
  overlayMaps(*last, mat);
  auto path = fb.build(config_.filename, config_.format);
  fileWriter_->write(path, mat, &t);
  if (config_.json) {
    fileWriter_->writeHeader(*first, path);
  }
}

std::string Himawari8ImageHandler::getBasename(const lrit::File& f) const {
  auto text = f.getHeader<lrit::AnnotationHeader>().text;

  // Find last _ in annotation text and use this prefix
  // as identification for this segmented image.
  // Example annotation: IMG_DK01VIS_201712162250_003.lrit
  auto pos = findLast(text, '_');
  ASSERT(pos != std::string::npos);
  return text.substr(0, pos);
}

struct timespec Himawari8ImageHandler::getTime(const lrit::File& f) const {
  struct timespec time = {0, 0};

  // Time of Himawari images is encoded in filename.
  // The LRIT time stamp header is bogus.
  // Example annotation: IMG_DK01VIS_201712162250_003.lrit
  auto text = f.getHeader<lrit::AnnotationHeader>().text;
  auto parts = split(text, '_');
  if (parts.size() != 4) {
    return time;
  }

  const char* buf = parts[2].c_str();
  const char* format = "%Y%m%d%H%M";
  struct tm tm;
  memset(&tm, 0, sizeof(tm));
  auto ptr = strptime(buf, format, &tm);

  // Only use time if strptime was successful.
  // The timestamp is UTC; use timegm so the result doesn't
  // depend on the local timezone of the machine running goesproc.
  if (ptr == (buf + 12)) {
    time.tv_sec = timegm(&tm);
    time.tv_nsec = 0;
  }

  return time;
}

void Himawari8ImageHandler::overlayMaps(const lrit::File& f, cv::Mat& mat) {
#ifdef HAS_PROJ
  if (config_.maps.empty()) {
    return;
  }

  auto inh = f.getHeader<lrit::ImageNavigationHeader>();
  auto lon = inh.getLongitude();

  // TODO: The map drawer should be cached by construction parameters.
  auto drawer = MapDrawer(&config_, lon, inh);
  mat = drawer.draw(mat);
#endif
}
