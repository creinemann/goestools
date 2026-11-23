#pragma once

#include <unordered_map>

#include "config.h"
#include "file_writer.h"
#include "handler.h"
#include "image.h"
#include "types.h"

// Handles Himawari-8/9 full disk imagery relayed over the GOES-West
// HRIT stream (NOAA product ID 43).
//
// Supports the same per-handler options as the GOES-R handler:
//   channels = [ "vs", "ir" ]        (also accepts "b03", "b13", "b08")
//   [handler.remap.<channel>]        contrast curve per channel
//   [handler.lut]                    2-channel false color LUT
class Himawari8ImageHandler : public Handler {
public:
  explicit Himawari8ImageHandler(
    const Config::Handler& config,
    const std::shared_ptr<FileWriter>& fileWriter);

  virtual void handle(std::shared_ptr<const lrit::File> f);

protected:
  std::string getBasename(const lrit::File& f) const;
  struct timespec getTime(const lrit::File& f) const;

  void overlayMaps(const lrit::File& f, cv::Mat& mat);

  bool matchChannel(const Channel& channel) const;

  std::unique_ptr<Image> buildImage(
    const std::vector<std::shared_ptr<const lrit::File>>& files,
    const Channel& channel) const;

  void handleFalseColor(
    std::shared_ptr<const lrit::File> first,
    std::shared_ptr<const lrit::File> last,
    const Region& region,
    const Channel& channel,
    std::unique_ptr<Image> image);

  Config::Handler config_;
  std::shared_ptr<FileWriter> fileWriter_;

  using SegmentVector = std::vector<std::shared_ptr<const lrit::File>>;

  // Maintain a map of region and channel to list of segments.
  // This assumes that two images for the same region and channel are
  // never sent concurrently, but always in order.
  std::unordered_map<
    SegmentKey,
    SegmentVector,
    SegmentKeyHash> segments_;

  // For false color: the first-to-arrive channel of a scan is kept
  // here until the other channel of the same scan time completes.
  struct Pending {
    std::shared_ptr<const lrit::File> first;
    std::shared_ptr<const lrit::File> last;
    Region region;
    Channel channel;
    time_t time;
    std::unique_ptr<Image> image;
  };
  std::unique_ptr<Pending> pending_;
};
