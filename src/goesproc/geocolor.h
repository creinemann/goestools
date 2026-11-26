#pragma once

#include <ctime>
#include <string>

#include <opencv2/opencv.hpp>

// USRG_GeoColor (USRadioguy addition)
//
// Natural Earth colors for full-disk false color images. The false
// color LUT keeps doing ocean, clouds and night; on land (from a fixed
// land mask) the color comes from NASA's Blue Marble Next Generation
// for the time of year, blended between the two nearest months, while
// all brightness still comes from the live visible channel. Very
// bright land (snow, salt flats, haze) fades to white and cold or
// bright cloud keeps the LUT color, so weather stays live.
//
// Data per satellite view, made by scripts/make_geocolor_data.py:
//   <dir>/<sat>_land.png        land mask (0..255, soft coastline)
//   <dir>/<sat>_tint_MM.jpg     Blue Marble month MM in this view
//   <dir>/luminance.png         256x1 brightness per visible level
//
// Configure in a false color handler:
//   [handler.geocolor]
//   path = "/usr/share/goestools/usradioguy/geocolor"
//   satellite = "goes19"      # goes19, goes18 or himawari9
//   strength = 1.0            # 1.0 = Blue Marble colors as they are
//
// Only full disk images are colored; other regions keep the LUT colors.
namespace geocolor {

struct Settings {
  std::string path;
  std::string satellite;
  float strength = 1.0f;

  bool enabled() const { return !path.empty(); }
};

// vis, ir: the remapped 8-bit inputs that indexed the LUT (rows, columns).
// out: the BGR false color image made from them; changed in place.
// Returns false (out unchanged) if the data files can't be loaded.
bool apply(
  const Settings& s,
  cv::Mat vis,
  cv::Mat ir,
  cv::Mat& out,
  time_t when);

// Weight of the second month for a date (months centred on the 15th).
// Sets m0/m1 to the two months (1..12) to blend.
float monthBlend(time_t when, int& m0, int& m1);

} // namespace geocolor
