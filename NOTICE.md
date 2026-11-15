# Notices and attribution

The project is distributed under **GPL-3.0-or-later**; see LICENSE and SPDX headers.

Trigger output encoding follows [dualsensectl-macos](https://github.com/alfaoz/dualsensectl-macos)
(commit 02dc1d50cc3307b502671cbc1f627d914be4991e), itself based on
[nowrep/dualsensectl](https://github.com/nowrep/dualsensectl). The original driver notice is
Copyright (c) 2020 Sony Interactive Entertainment. Preserve that notice.
The optional C oracle compiles against the user's own upstream source; upstream sources/binaries
are not bundled here. The golden output fixtures contain generated trigger command packets.

Wii U v208 pointer/equipment leads came from
[WiiXLaunch-BotW](https://github.com/BladesawStudios/wiixlaunch-botw), particularly
[player.hpp](https://github.com/BladesawStudios/wiixlaunch-botw/blob/main/include/wiixlaunch/botw/game/player.hpp),
[pouch.hpp](https://github.com/BladesawStudios/wiixlaunch-botw/blob/main/include/wiixlaunch/botw/game/pouch.hpp)
and its symbols-wiiu-v208.csv (GPL-3.0). Leads were checked against live Wii U functions and objects.
Bow-state/menu correlations were investigated separately in the original development session.
No upstream WiiXLaunch implementation is bundled.

Protocol/API references:

* [HIDAPI Darwin API](https://github.com/libusb/hidapi/blob/hidapi-0.15.0/hidapi/hidapi_darwin.h).
* [SDL PS5 report structures](https://github.com/libsdl-org/SDL/blob/SDL2/src/joystick/hidapi/SDL_hidapi_ps5.c).
* [Linux hid-playstation driver](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c).
* [Cemu source at the tested commit](https://github.com/cemu-project/Cemu/tree/3005cb7).

This repository does not contain Nintendo game executables/assets/saves, Cemu binaries,
proprietary SDKs, HIDAPI binaries, or private development captures. The C reader is built locally.

PlayStation, DualSense, Nintendo, The Legend of Zelda and Breath of the Wild are trademarks
of their respective owners. This community project is not affiliated with or endorsed by them
or by the Cemu project.
