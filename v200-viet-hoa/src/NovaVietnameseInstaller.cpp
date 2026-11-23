#include "NovaVietnameseInstaller.hpp"
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_set>
#include <vector>
#include <system_error>
#include <unistd.h>
namespace fs = std::filesystem;
namespace nova_vi {
namespace {
struct Entry { std::string path; uint64_t offset = 0, size = 0; };
constexpr uint64_t MAX_INDEX = 4 * 1024 * 1024;
constexpr uint64_t MAX_PAYLOAD = 64 * 1024 * 1024;
constexpr size_t MAX_ENTRIES = 4096;

bool SafeGamePath(const std::string& path) {
  if (path.empty() || path.front() == '/' || path.find('\\') != std::string::npos || path.find(':') != std::string::npos) return false;
  if (path.rfind("x64/", 0) != 0 && path.rfind("common/", 0) != 0) return false;
  if (path.find("//") != std::string::npos) return false;
  for (const auto& component : fs::path(path)) if (component.empty() || component == "." || component == "..") return false;
  std::string suffix = fs::path(path).extension().string();
  for (auto& ch : suffix) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
  if (suffix != ".gxt2" && suffix != ".xml" && suffix != ".gfx" && suffix != ".ytd") return false;
  for (unsigned char ch : path) {
    if (!std::isalnum(ch) && ch != '/' && ch != '-' && ch != '_' && ch != '.') return false;
  }
  return true;
}

struct Reader {
  const std::string& data;
  size_t cursor = 0;
  void White() { while (cursor < data.size() && (data[cursor] == ' ' || data[cursor] == '\n' || data[cursor] == '\r' || data[cursor] == '\t')) ++cursor; }
  bool Eat(char c) { White(); if (cursor >= data.size() || data[cursor] != c) return false; ++cursor; return true; }
  bool Path(std::string& out) {
    White(); if (!Eat('"')) return false; size_t start=cursor;
    while(cursor < data.size() && data[cursor] != '"') {
      if (data[cursor] == '\\' || static_cast<unsigned char>(data[cursor]) < 32) return false;
      ++cursor;
    }
    if (cursor == data.size()) return false;
    out.assign(data.data()+start,cursor-start); ++cursor; return SafeGamePath(out);
  }
  bool Number(uint64_t& n) {
    White(); if(cursor >= data.size() || !std::isdigit(static_cast<unsigned char>(data[cursor]))) return false;
    n = 0;
    while(cursor<data.size() && std::isdigit(static_cast<unsigned char>(data[cursor]))) {
      const unsigned d = static_cast<unsigned>(data[cursor++]-'0');
      if(n>(std::numeric_limits<uint64_t>::max()-d)/10) return false;
      n=n*10+d;
    }
    return true;
  }
};

bool ParseIndex(const std::string& index, uint64_t payloadSize, std::vector<Entry>& out) {
  Reader r{index}; if(!r.Eat('[')) return false;
  std::unordered_set<std::string> paths;
  uint64_t next=0;
  if(r.Eat(']')) return false;
  do {
    Entry e;
    if(!r.Eat('[') || !r.Path(e.path) || !r.Eat(',') || !r.Number(e.offset) || !r.Eat(',') || !r.Number(e.size) || !r.Eat(']')) return false;
    if(e.offset!=next || e.size > payloadSize-next || out.size() >= MAX_ENTRIES) return false;
    std::string lower=e.path;
    std::transform(lower.begin(),lower.end(),lower.begin(),[](unsigned char c){return std::tolower(c);});
    if(!paths.insert(lower).second) return false;
    next+=e.size; out.emplace_back(std::move(e));
    if(r.Eat(']')) break;
    if(!r.Eat(',')) return false;
  } while(true);
  r.White(); return !out.empty() && r.cursor == index.size() && next == payloadSize;
}

bool CopyEntry(std::ifstream& source, const fs::path& target, uint64_t offset, uint64_t count) {
  if(count > MAX_PAYLOAD) return false;
  source.clear(); source.seekg(static_cast<std::streamoff>(offset),std::ios::beg);
  if(!source) return false;
  std::ofstream output(target,std::ios::binary|std::ios::trunc);
  if(!output) return false;
  std::array<char, 65536> buffer{};
  while(count) {
    const size_t n=static_cast<size_t>(std::min<uint64_t>(count,buffer.size()));
    source.read(buffer.data(),static_cast<std::streamsize>(n));
    if(source.gcount()!=static_cast<std::streamsize>(n)) return false;
    output.write(buffer.data(),static_cast<std::streamsize>(n));
    if(!output) return false;
    count-=n;
  }
  output.flush(); return output.good();
}

bool EqualEntry(std::ifstream& source, const fs::path& target, uint64_t offset, uint64_t count) {
  std::ifstream current(target,std::ios::binary|std::ios::ate);
  if(!current || current.tellg()<0 || static_cast<uint64_t>(current.tellg())!=count) return false;
  current.seekg(0,std::ios::beg);
  source.clear();source.seekg(static_cast<std::streamoff>(offset),std::ios::beg);
  if(!source) return false;
  std::array<char,65536> a{},b{};
  while(count) {
    const auto n=static_cast<std::streamsize>(std::min<uint64_t>(count,a.size()));
    source.read(a.data(),n);current.read(b.data(),n);
    if(source.gcount()!=n || current.gcount()!=n || !std::equal(a.begin(),a.begin()+n,b.begin())) return false;
    count-=static_cast<uint64_t>(n);
  }
  return true;
}

uint64_t HashFile(std::ifstream& in) {
  in.clear(); in.seekg(0,std::ios::beg);
  uint64_t h=14695981039346656037ull;
  std::array<char,65536> buf{};
  while(in) {
    in.read(buf.data(),buf.size());
    for(std::streamsize i=0;i<in.gcount();++i) {h^=static_cast<unsigned char>(buf[static_cast<size_t>(i)]);h*=1099511628211ull;}
  }
  return h;
}
}
Result Install(const std::string& nvp_path, const std::string& mods_directory) {
  Result res;
  std::ifstream pack(nvp_path,std::ios::binary|std::ios::ate);
  if(!pack) {res.message="NOVAPAK1 file unavailable";return res;}
  const auto len=pack.tellg();
  if(len<16 || static_cast<uint64_t>(len)>MAX_PAYLOAD+MAX_INDEX+16) {res.message="NOVAPAK1 size invalid";return res;}
  pack.seekg(0);
  std::array<unsigned char,16> header{};
  pack.read(reinterpret_cast<char*>(header.data()),header.size());
  if(!pack || std::string(reinterpret_cast<const char*>(header.data()),8)!="NOVAPAK1") {res.message="NOVAPAK1 magic invalid";return res;}
  uint64_t indexLength=0;
  for(unsigned i=0;i<8;++i) indexLength|=static_cast<uint64_t>(header[8+i])<<(8*i);
  if(indexLength==0 || indexLength>MAX_INDEX || indexLength+16>=static_cast<uint64_t>(len)) {res.message="NOVAPAK1 index length invalid";return res;}
  std::string index(static_cast<size_t>(indexLength),'\0');
  pack.read(index.data(),static_cast<std::streamsize>(indexLength));
  if(!pack) {res.message="NOVAPAK1 index unreadable";return res;}
  const uint64_t payloadStart=indexLength+16;
  std::vector<Entry> entries;
  if(!ParseIndex(index,static_cast<uint64_t>(len)-payloadStart,entries)) {res.message="NOVAPAK1 index validation failed";return res;}
  const uint64_t packFingerprint=HashFile(pack);
  std::ostringstream tag;
  tag<<len<<"-"<<std::hex<<std::setfill('0')<<std::setw(16)<<packFingerprint;
  std::error_code ec;
  const fs::path mods=fs::path(mods_directory).lexically_normal();
  if(mods.empty() || mods.filename()!="Mods") {res.message="Expected Documents/Mods directory";return res;}
  const fs::path docs=mods.parent_path();
  const fs::path marker=docs/".mugoat_v200_vietnamese_install";
  const fs::path stage=docs/(".mugoat_v200_stage."+std::to_string(static_cast<long long>(getpid())));
  if(fs::is_symlink(fs::symlink_status(mods,ec)) || fs::is_symlink(fs::symlink_status(docs,ec))) {
    res.message="Mods/Documents symlink not supported";return res;
  }
  ec.clear();
  if(fs::exists(marker,ec)) {
    if(ec) {res.message="Cannot inspect install marker";return res;}
    std::ifstream m(marker);
    std::string existing;std::getline(m,existing);
    if(existing!=tag.str()) {res.message="Different Vietnamese pack installed; uninstall first";return res;}
    for(const auto& e:entries) {
      ec.clear();const fs::path target=mods/fs::path(e.path);
      if(!fs::is_regular_file(target,ec) || ec) {res.message="Install marker present but a resource is missing: "+e.path;return res;}
      if(!EqualEntry(pack,target,payloadStart+e.offset,e.size)) {
        res.message="Installed resource differs from source pack (will not overwrite): "+e.path;return res;
      }
    }
    res.ok=true;res.files=entries.size();res.message="Already installed (paths present)";return res;
  }
  if(ec) {res.message="Cannot inspect install marker";return res;}
  for(const auto& e:entries) {
    fs::path target=mods/fs::path(e.path);
    for(fs::path p=target; p!=mods && p!=docs; p=p.parent_path()) {
      ec.clear();const auto st=fs::symlink_status(p,ec);
      if(ec && ec!=std::errc::no_such_file_or_directory) {
        res.message="Cannot inspect path: "+p.string();return res;
      }
      if(fs::is_symlink(st)) {res.message="Unsafe symlink in Mods path: "+e.path;return res;}
    }
    ec.clear();if(fs::exists(target,ec) || ec) {res.message="File already present; no files overwritten: "+e.path;return res;}
  }
  ec.clear();fs::create_directories(mods,ec);
  if(ec) {res.message="Cannot create Mods folder: "+ec.message();return res;}
  if(fs::exists(stage,ec) || ec) {res.message="Old staging directory exists";return res;}
  ec.clear();if(!fs::create_directory(stage,ec) || ec) {res.message="Cannot create staging directory: "+ec.message();return res;}
  auto fail_stage=[&](const std::string& why)->Result {
    std::error_code ignored;fs::remove_all(stage,ignored);res.message=why;return res;
  };
  for(const auto& e:entries) {
    const fs::path dest=stage/fs::path(e.path);
    ec.clear();fs::create_directories(dest.parent_path(),ec);
    if(ec) return fail_stage("Cannot create staged resource dir: "+ec.message());
    if(!CopyEntry(pack,dest,payloadStart+e.offset,e.size)) return fail_stage("Copy failed for "+e.path);
  }
  std::vector<fs::path> installed;
  auto rollback=[&](const std::string& why)->Result {
    for(auto it=installed.rbegin();it!=installed.rend();++it) {std::error_code ignored;fs::remove(*it,ignored);}
    std::error_code ignored;fs::remove_all(stage,ignored);res.message=why;return res;
  };
  for(const auto& e:entries) {
    const fs::path target=mods/fs::path(e.path);
    ec.clear();fs::create_directories(target.parent_path(),ec);
    if(ec) return rollback("Cannot create Mods subdirectory: "+ec.message());
    ec.clear();if(fs::exists(target,ec) || ec) return rollback("Conflict while committing: "+e.path);
    ec.clear();fs::rename(stage/fs::path(e.path),target,ec);
    if(ec) return rollback("Commit failed for "+e.path+": "+ec.message());
    installed.push_back(target);
  }
  const fs::path markerTmp=docs/(".mugoat_v200_marker."+std::to_string(static_cast<long long>(getpid())));
  {
    std::ofstream m(markerTmp,std::ios::binary|std::ios::trunc);
    if(!m) return rollback("Cannot create completion marker");
    m<<tag.str()<<"\n";m.close();
    if(!m) {std::error_code ignored;fs::remove(markerTmp,ignored);return rollback("Cannot write completion marker");}
  }
  ec.clear();fs::rename(markerTmp,marker,ec);
  if(ec) {std::error_code ignored;fs::remove(markerTmp,ignored);return rollback("Cannot finalize install marker");}
  ec.clear();fs::remove_all(stage,ec);
  res.ok=true;res.changed=true;res.files=entries.size();res.message="Installed Vietnamese resource paths in Mods root";return res;
}
}
