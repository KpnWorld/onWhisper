{ pkgs }: {
    deps = [
        pkgs.python3
        pkgs.python3Packages.pip
        pkgs.ffmpeg
        pkgs.opus
        pkgs.libopus
        pkgs.pkg-config
    ];
}