/* SPDX-License-Identifier: GPL-3.0-or-later
 * Independent oracle: compile against the user's unmodified dualsensectl-macos.
 * No hardware is opened; only hid_write is intercepted.
 * cc -I/path/to/dualsensectl-macos -I/opt/homebrew/opt/hidapi/include/hidapi \
 *   -DDUALSENSECTL_VERSION='"0.7.0"' tools/reference_packets.c \
 *   -L/opt/homebrew/opt/hidapi/lib -lhidapi -framework IOKit \
 *   -framework CoreFoundation -o /tmp/reference_packets
 */
#define main upstream_main
#define hid_write capture_write
#include "main.c"
#undef main
#undef hid_write

int capture_write(hid_device *dev, const unsigned char *data, size_t length)
{
    (void)dev;
    for (size_t i = 0; i < length; i++) printf("%02x", data[i]);
    puts("");
    return (int)length;
}

int main(void)
{
    struct dualsense ds = {0};
    ds.bt = true;
    for (int i = 0; i < 16; i++) command_trigger_bow(&ds, "right", 2, 5, 8, 4);
    for (int i = 0; i < 16; i++) command_trigger_off(&ds, "right");
    return 0;
}
