#include "geocolor.h"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <map>
#include <mutex>

namespace geocolor {

namespace {

// Small files, loaded once and kept: land masks, monthly tints, luminance.
std::map<std::string, cv::Mat> cache;
std::mutex cacheMutex;

cv::Mat load(const std::string& path, int flags) {
  std::lock_guard<std::mutex> lock(cacheMutex);
  auto it = cache.find(path);
  if (it != cache.end()) {
    return it->second;
  }
  cv::Mat m = cv::imread(path, flags);
  if (!m.data) {
    std::cerr << "USRG_GeoColor: unable to load " << path << std::endl;
  }
  cache[path] = m;
  return m;
}

inline float clamp01(float v) {
  return v < 0.0f ? 0.0f : (v > 1.0f ? 1.0f : v);
}

int daysInMonth(int year, int month) {
  static const int d[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
  if (month == 2 && ((year % 4 == 0 && year % 100 != 0) || year % 400 == 0)) {
    return 29;
  }
  return d[month - 1];
}

} // namespace

float monthBlend(time_t when, int& m0, int& m1) {
  struct tm tm;
  gmtime_r(&when, &tm);
  const int year = tm.tm_year + 1900;
  const int month = tm.tm_mon + 1;
  // Position within the month in days, with the 15th (00:00) as the centre.
  const float day = (tm.tm_mday - 1) + (tm.tm_hour + tm.tm_min / 60.0f) / 24.0f;
  const float mid = 14.0f;
  if (day >= mid) {
    m0 = month;
    m1 = month % 12 + 1;
    // From this month's 15th to next month's 15th
    float span = daysInMonth(year, month);
    return (day - mid) / span;
  }
  m1 = month;
  m0 = (month + 10) % 12 + 1;
  // From last month's 15th to this month's 15th
  int prevYear = month == 1 ? year - 1 : year;
  float span = daysInMonth(prevYear, m0);
  return (day + span - mid) / span;
}

bool apply(
    const Settings& s,
    cv::Mat vis,
    cv::Mat ir,
    cv::Mat& out,
    time_t when) {
  if (!s.enabled() || out.type() != CV_8UC3) {
    return false;
  }

  const auto base = s.path + "/" + s.satellite;
  cv::Mat land = load(base + "_land.png", cv::IMREAD_GRAYSCALE);
  cv::Mat lumtab = load(s.path + "/luminance.png", cv::IMREAD_GRAYSCALE);
  int m0 = 1;
  int m1 = 2;
  const float t = monthBlend(when, m0, m1);
  char name[32];
  snprintf(name, sizeof(name), "_tint_%02d.jpg", m0);
  cv::Mat tint0 = load(base + name, cv::IMREAD_COLOR);
  snprintf(name, sizeof(name), "_tint_%02d.jpg", m1);
  cv::Mat tint1 = load(base + name, cv::IMREAD_COLOR);
  if (!land.data || !lumtab.data || lumtab.total() != 256 ||
      !tint0.data || !tint1.data || tint0.size() != tint1.size()) {
    return false;
  }

  const cv::Size size = out.size();

  // Inputs at the output size (the false color code may have resized one)
  if (vis.size() != size) {
    cv::Mat tmp;
    cv::resize(vis, tmp, size);
    vis = tmp;
  }
  if (ir.size() != size) {
    cv::Mat tmp;
    cv::resize(ir, tmp, size);
    ir = tmp;
  }

  // Blend the two months at their stored size, then scale to the image.
  cv::Mat tint;
  cv::addWeighted(tint0, 1.0 - t, tint1, t, 0.0, tint);
  cv::Mat tintFull;
  cv::resize(tint, tintFull, size, 0, 0, cv::INTER_LINEAR);
  tint.release();
  cv::Mat landFull;
  cv::resize(land, landFull, size, 0, 0, cv::INTER_LINEAR);

  // Per visible level (row) and per infrared level (column) factors.
  float lum[256], white[256], cloudRow[256], cloudCol[256], cold[256];
  for (int v = 0; v < 256; v++) {
    lum[v] = lumtab.data[v];
    white[v] = clamp01((v - 165) / 55.0f);   // very bright land -> white
    cloudRow[v] = clamp01((v - 125) / 45.0f); // bright ...
    cloudCol[v] = clamp01((v - 36) / 10.0f);  // ... and not hot = cloud
    cold[v] = clamp01((v - 58) / 14.0f);      // cold = cloud
  }
  const float strength = s.strength;

  for (int y = 0; y < size.height; y++) {
    const uint8_t* pv = vis.ptr<uint8_t>(y);
    const uint8_t* pi = ir.ptr<uint8_t>(y);
    const uint8_t* pm = landFull.ptr<uint8_t>(y);
    const uint8_t* pt = tintFull.ptr<uint8_t>(y);
    uint8_t* po = out.ptr<uint8_t>(y);
    for (int x = 0; x < size.width; x++) {
      const uint8_t m8 = pm[x];
      if (m8 == 0) {
        continue;  // ocean / space: LUT colors as they are
      }
      const float m = m8 / 255.0f;
      const int r = pv[x];
      const int c = pi[x];
      const float L = lum[r];

      // Land color this time of year, at unit brightness (BGR)
      const float tb = pt[x * 3 + 0];
      const float tg = pt[x * 3 + 1];
      const float tr = pt[x * 3 + 2];
      const float tl = std::max(0.299f * tr + 0.587f * tg + 0.114f * tb, 6.0f);
      const float k = std::max(cloudRow[r] * cloudCol[c], cold[c]);
      const float w = white[r];

      const float tch[3] = {tb, tg, tr};
      for (int ch = 0; ch < 3; ch++) {
        float chroma = 1.0f + (tch[ch] / tl - 1.0f) * strength;
        float v = std::min(std::max(chroma * L, 0.0f), 255.0f);
        v = v * (1.0f - w) + L * w;               // snow / salt -> white
        const float cur = po[x * 3 + ch];
        v = v * (1.0f - k) + cur * k;             // cloud keeps LUT color
        v = v * m + cur * (1.0f - m);             // soft coastline
        po[x * 3 + ch] = (uint8_t) std::lrint(std::min(std::max(v, 0.0f), 255.0f));
      }
    }
  }
  return true;
}

void fuse(cv::Mat& out, const cv::Mat& enhanced, float strength) {
  if (out.size() != enhanced.size() || out.type() != CV_8UC3 || enhanced.type() != CV_8UC3) {
    std::cerr << "USRG_GeoFusion: image sizes differ, skipped" << std::endl;
    return;
  }
  strength = std::max(0.0f, std::min(1.0f, strength));

  // Colorfulness of the enhancement: grey/white/black = 0, colors = high.
  cv::Mat alpha(out.size(), CV_32F);
  cv::Mat solid(out.size(), CV_8U);
  for (int y = 0; y < out.rows; y++) {
    const uint8_t* e = enhanced.ptr<uint8_t>(y);
    float* a = alpha.ptr<float>(y);
    uint8_t* m = solid.ptr<uint8_t>(y);
    for (int x = 0; x < out.cols; x++) {
      int b = e[3 * x], g = e[3 * x + 1], r = e[3 * x + 2];
      int chroma = std::max(b, std::max(g, r)) - std::min(b, std::min(g, r));
      float v = std::min(1.0f, std::max(0.0f, (chroma - 28) / 42.0f));
      a[x] = v;
      m[x] = v > 0.5f ? 1 : 0;
    }
  }

  // Close small gaps (dark steps in the color scale, map lines crossing
  // colored cloud) and fill small enclosed holes, so storms stay solid.
  // Sizes are for a 5424 px full disk and scale with the image.
  const double scale = out.cols / 5424.0;
  int k = std::max(3, int(std::lround(5 * scale)) | 1);
  cv::morphologyEx(solid, solid, cv::MORPH_CLOSE,
                   cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(k, k)));
  cv::Mat inv = 1 - solid, labels, stats, centroids;
  int n = cv::connectedComponentsWithStats(inv, labels, stats, centroids, 8);
  const int maxHole = std::max(20, int(300 * scale * scale));
  std::vector<uint8_t> small(n, 0);
  for (int i = 1; i < n; i++) {
    small[i] = stats.at<int>(i, cv::CC_STAT_AREA) < maxHole;
  }
  for (int y = 0; y < out.rows; y++) {
    const int* l = labels.ptr<int>(y);
    uint8_t* m = solid.ptr<uint8_t>(y);
    for (int x = 0; x < out.cols; x++) {
      if (!m[x] && small[l[x]]) m[x] = 1;
    }
  }
  cv::Mat soft;
  solid.convertTo(soft, CV_32F);
  cv::GaussianBlur(soft, soft, cv::Size(5, 5), 0);
  cv::max(alpha, soft, alpha);

  for (int y = 0; y < out.rows; y++) {
    uint8_t* o = out.ptr<uint8_t>(y);
    const uint8_t* e = enhanced.ptr<uint8_t>(y);
    const float* a = alpha.ptr<float>(y);
    for (int x = 0; x < out.cols; x++) {
      float w = a[x] * strength;
      if (w <= 0.0f) continue;
      for (int c = 0; c < 3; c++) {
        o[3 * x + c] = uint8_t(o[3 * x + c] * (1.0f - w) + e[3 * x + c] * w + 0.5f);
      }
    }
  }
}

} // namespace geocolor
