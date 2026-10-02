# Installation

## Linux (mainstream distributions)

Works on Ubuntu, Debian, RHEL, CentOS, Fedora, Raspberry Pi OS, Amazon Linux, openSUSE, Oracle Linux, and VMware Photon OS.

Do not pipe a remote script into a shell. Do not download or run `https://tailscale.com/install.sh`.

Install the `tailscale` package with the distro package manager, or have the user install from https://tailscale.com/download. After that package is installed:

```bash
sudo tailscale up
```

The `tailscale up` command prints a URL to authenticate. Open it in a browser to add the device to your tailnet.

### Verify installation

```bash
tailscale ip        # Shows your Tailscale IPv4 and IPv6 addresses
tailscale status    # Shows connection status and other devices
```

### Arch Linux and NixOS

These distributions have their own packages — install `tailscale` through `pacman` or your NixOS configuration respectively.

### Static binaries

Do not download an unpinned tarball, and do not start `tailscaled` from an archive you fetched. If the distro has no package, the user picks one version from https://pkgs.tailscale.com/stable/, checks it, and unpacks it themselves. A systemd unit is in the archive's `systemd/` directory.

## macOS

Three variants are available:

1. **Mac App Store** — GUI app, sandboxed, most common for personal use
2. **Standalone (GUI)** — Downloaded from http://tailscale.com/download, same GUI but not sandboxed
3. **Open source CLI (`tailscaled`)** — Command-line only, required for Tailscale SSH server

Download from https://tailscale.com/download/mac or the Mac App Store.

For CLI access with the GUI variants, enable CLI integration in the Tailscale menu, or invoke directly:
```bash
/Applications/Tailscale.app/Contents/MacOS/Tailscale <command>
```

## Windows

Download from https://tailscale.com/download/windows or install via MSI for enterprise deployment.

WSL 2 is also supported; refer to the Tailscale docs for WSL 2 instructions.

## iOS and Android

Install from the Apple App Store or Google Play Store respectively. Authentication happens in-app.

## Updating

- **CLI**: `tailscale update`
- **GUI apps**: Update through the app or app store
- **Auto-update**: Configurable from the admin console or via MDM policies

## Uninstalling

Refer to Tailscale's uninstall documentation for platform-specific removal steps. On Linux, use your package manager (`apt remove tailscale`, `yum remove tailscale`).
