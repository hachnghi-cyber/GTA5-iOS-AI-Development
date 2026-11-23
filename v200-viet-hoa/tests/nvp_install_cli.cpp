#include "NovaVietnameseInstaller.hpp"
#include <iostream>
int main(int argc, char **argv) {
  if (argc != 3) { std::cerr << "Usage: nvp_install <pack.nvp> <Mods-folder>\n"; return 2; }
  const auto r = nova_vi::Install(argv[1], argv[2]);
  std::cout << "ok=" << r.ok << " changed=" << r.changed
            << " count=" << r.files << " message=" << r.message << "\n";
  return r.ok ? 0 : 1;
}
