# Ola Dash

The product built on the [Ola Dash SDK](https://github.com/abhi245y/ola-dash-sdk): an unofficial dash for the Ola S1 Pro Gen 1 electric scooter. This repo holds the theme pack, installer, recovery watchdog, store index, release pipeline and owner docs.

It is not the host app, the theme contract or the plugin API. Those live in the SDK, which is pinned here as a submodule at `sdk/` (the last pushed SDK commit). Start with the SDK's [README](https://github.com/abhi245y/ola-dash-sdk#readme) and `sdk/docs/`. The roadmap is in [docs/plan/PLAN.md](docs/plan/PLAN.md).

## Build

```sh
git submodule update --init
tools/build.sh                 # APK in out/
SDK_DIR=../ola-dash-sdk tools/build.sh   # build an unpushed SDK checkout instead
```

The build runs on `arlp-pc` over ssh and bundles every theme in `themes/` into the APK. `themes/minimal` is a copy from the SDK, a placeholder until E4.

## Disclaimer

Ola Dash is an unofficial, community project. It is not affiliated with, authorized by, sponsored by, or endorsed by Ola Electric. "Ola" and "S1" are trademarks of Ola Electric, used only to describe compatibility. Installing the host replaces the stock home screen on a scooter you own and may affect its warranty. You use this software at your own risk. Riding with experimental software is your responsibility.

## License

Free software under the [GNU General Public License v3.0 or later](LICENSE).
