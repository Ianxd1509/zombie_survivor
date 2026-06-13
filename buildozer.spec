[app]

title = Virus
package.name = virus
package.domain = org.zombie
source.dir = .
source.include_exts = py,png,jpg,wav,txt,json,md
version = 1.0
requirements = python3, pygame, hostpython3
orientation = landscape
fullscreen = 1
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE
android.api = 31
android.minapi = 21
android.sdk = /home/runner/android-sdk
android.ndk = /home/runner/.buildozer/android/platform/android-ndk-r25c
android.build_tools = 34.0.0
android.archs = arm64-v8a
android.wakelock = 1
android.enable_androidx = 1
android.add_src =
android.gradle_dependencies =

[buildozer]
log_level = 2
warn_on_root = 0
