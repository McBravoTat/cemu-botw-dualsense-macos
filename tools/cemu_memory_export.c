// SPDX-License-Identifier: GPL-3.0-or-later
// Experimental in-process, read-only guest-memory exporter for one verified Cemu binary.
// Does not expose a TCP port or implement writes/calls into guest code.
#include <arpa/inet.h>
#include <dlfcn.h>
#include <errno.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <mach-o/dyld.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

static uintptr_t *base_pointer;
static const unsigned char *running_pointer;
static const uint64_t *title_pointer;

static kern_return_t safe_read(uintptr_t address, void *buffer, size_t size) {
    mach_vm_size_t actual = 0;
    kern_return_t r = mach_vm_read_overwrite(mach_task_self(), address, size,
                                            (mach_vm_address_t)buffer, &actual);
    return r == KERN_SUCCESS && actual == size ? KERN_SUCCESS : KERN_INVALID_ADDRESS;
}

static uintptr_t guest_base(void) {
    uintptr_t base = 0;
    if (!base_pointer || safe_read((uintptr_t)base_pointer, &base, sizeof(base))) return 0;
    return base;
}

static void *serve(void *unused) {
    (void)unused;
    // dlsym uses symbol names without Mach-O's leading underscore.
    base_pointer = dlsym(RTLD_DEFAULT, "memory_base");
    running_pointer = dlsym(RTLD_DEFAULT, "_ZN10CafeSystem14sSystemRunningE");
    title_pointer = dlsym(RTLD_DEFAULT, "_ZN10CafeSystem18sForegroundTitleIdE");
    if (!base_pointer || !running_pointer || !title_pointer) {
        fprintf(stderr, "[BOTW read-only export] required Cemu symbols unavailable; refusing startup\n");
        return NULL;
    }
    char path[104];
    snprintf(path, sizeof(path), "/private/tmp/cemu-botw-%d.sock", getpid());
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return NULL;
    struct sockaddr_un address = {0};
    address.sun_family = AF_UNIX;
    strncpy(address.sun_path, path, sizeof(address.sun_path) - 1);
    // Refuse an existing path. Never unlink another process's socket.
    if (bind(fd, (struct sockaddr *)&address, sizeof(address)) != 0) {
        fprintf(stderr, "[BOTW read-only export] bind failed: %s\n", strerror(errno));
        close(fd); return NULL;
    }
    if (chmod(path, S_IRUSR | S_IWUSR) != 0) {
        close(fd); unlink(path); return NULL;
    }
    if (listen(fd, 2) != 0) { close(fd); unlink(path); return NULL; }
    fprintf(stderr, "[BOTW read-only export] socket=%s, shared memory reads only\n", path);
    for (;;) {
        int client = accept(fd, NULL, NULL);
        if (client < 0) continue;
        int no_sigpipe = 1;
        setsockopt(client, SOL_SOCKET, SO_NOSIGPIPE, &no_sigpipe, sizeof(no_sigpipe));
        struct timeval timeout = {.tv_sec = 10};
        setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
        setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
        FILE *stream = fdopen(client, "r+");
        if (!stream) { close(client); continue; }
        setvbuf(stream, NULL, _IONBF, 0);
        char command[128];
        while (fgets(command, sizeof(command), stream)) {
            if (!strchr(command, '\n')) {
                fputs("ERR command-too-long\n", stream); break;
            }
            if (!strcmp(command, "info\n")) {
                unsigned char running = 0;
                uint64_t title = 0;
                int has_running = running_pointer && !safe_read((uintptr_t)running_pointer, &running, 1);
                if (title_pointer) safe_read((uintptr_t)title_pointer, &title, sizeof(title));
                fprintf(stream, "{\"pid\":%d,\"base\":\"0x%llx\",\"running\":%s,\"title_id\":\"%016llx\",\"read_only\":true}\n",
                        getpid(), (unsigned long long)guest_base(),
                        has_running ? (running ? "true" : "false") : "null",
                        (unsigned long long)title);
                continue;
            }
            unsigned long long guest;
            unsigned size;
            char extra;
            if (sscanf(command, "read %llx %u %c", &guest, &size, &extra) != 2 ||
                guest < 0x01000000 || guest >= 0x50000000ULL || size == 0 || size > 65536 ||
                size > 0x50000000ULL - guest) {
                fputs("ERR invalid-range-or-command\n", stream); continue;
            }
            uintptr_t base = guest_base();
            unsigned char buffer[65536];
            if (!base || safe_read(base + guest, buffer, size) != KERN_SUCCESS) {
                fputs("ERR unmapped\n", stream); continue;
            }
            fprintf(stream, "OK %u\n", size);
            if (fwrite(buffer, 1, size, stream) != size) break;
        }
        fclose(stream);
    }
    return NULL;
}

__attribute__((constructor)) static void start_export(void) {
    pthread_t thread;
    if (!pthread_create(&thread, NULL, serve, NULL)) pthread_detach(thread);
}
