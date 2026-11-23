#pragma once
#include <cstddef>
#include <string>
namespace nova_vi {
struct Result {
  bool ok = false;
  bool changed = false;
  size_t files = 0;
  std::string message;
};
// Install NOVAPAK1 resources into Documents/Mods game-relative paths.
// Does not bypass or alter Online restrictions.
Result Install(const std::string& nvp_path, const std::string& mods_directory);
}
