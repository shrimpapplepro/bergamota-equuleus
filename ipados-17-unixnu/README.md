# iPadOS 17.7.11 on the Mi 8 Pro (UniXNU), the earlier attempt

This was the first port. It reached the lock screen and home screen with touch working, but it has an iPad interface,
software drawing only, and is missing the deletable apps. The iOS 18 port in the root of this repository replaced it.

These are only the changes made for this phone, on top of
[keyfan/UniXNU-enchilada-bringup](https://github.com/keyfan/UniXNU-enchilada-bringup) at `d309f46`:

- `changes-against-enchilada-bringup-d309f46.patch`: edits to existing files
- `new-files/`: files added for this phone

To build, you also need UniXNU, Mu-Silicium, and the Dipper UEFI pieces from
[hanyaa380/UniXNU-dipper](https://github.com/hanyaa380/UniXNU-dipper), which `make-equuleus-uefi.py` reuses and which are not copied here.

`drivers/NativeUfs/RootLayout.h` is changed so the root is found by the GPT name `ios_root`. Do not revert that on a phone
where `userdata` holds Android.
