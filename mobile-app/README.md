# Bot Control mobile app

Android app for the existing bot administration dashboard. It opens the live
`/admin` control center, supports its HTTP Basic authentication, and keeps all
bot secrets and business logic on the server.

## Build

Install Android Studio (Android SDK 35), open this directory, let Gradle sync,
then choose **Build > Build APK(s)**. The debug APK is written to:

`app/build/outputs/apk/debug/app-debug.apk`

Alternatively, push the project to GitHub and run the included **Android APK**
workflow. Its `bot-control-debug-apk` artifact contains the installable APK.

The default server is configured in
`app/src/main/res/values/strings.xml`. It can also be changed inside the app
from **Server address**. Only HTTPS addresses are accepted.

## Security

The dashboard password is stored in the app's private preferences and is never
compiled into the APK. Android backups are disabled. For a public production
release, replace Basic authentication with short-lived server sessions and use
Android Keystore-backed encrypted storage.

## iOS

The same dashboard can be wrapped with `WKWebView`, but an iOS archive/IPA must
be compiled and signed on macOS with Xcode and an Apple Developer account.
