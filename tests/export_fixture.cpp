// SPDX-License-Identifier: GPL-3.0-or-later
// Synthetic Cemu-like host for exporter tests. No game code or assets.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <sys/mman.h>
#include <unistd.h>

extern "C" { void *memory_base = nullptr; }
namespace CafeSystem {
    bool sSystemRunning = true;
    uint64_t sForegroundTitleId = 0x00050000101c9500ULL;
}

int main() {
    const size_t size = 0x10010000;
    void *space = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    if (space == MAP_FAILED) return 1;
    memory_base = space;
    const unsigned char data[] = {0x12,0x34,0x56,0x78};
    memcpy(static_cast<unsigned char *>(space) + 0x10000000, data, sizeof(data));
    mprotect(static_cast<unsigned char *>(space) + 0x01000000, 0x10000, PROT_NONE);
    puts("READY"); fflush(stdout);
    while (getchar() != EOF) {}
    munmap(space, size);
    return 0;
}
