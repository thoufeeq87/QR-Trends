TSUKIYO OS - ANDROID APP (Android Studio project)
Shows your Tsukiyo OS site full screen and gives it the phone's real Wi-Fi, Bluetooth, SIM, battery, camera and file access.
NOT compiled by me (this machine cannot download the Android SDK). If Android Studio shows an error, send me the first red line.

1. Open ONLY this folder: Android Studio > File > Open > pick the "TsukiyoAndroid" folder (the one containing settings.gradle). Do not paste scripts into another project.
2. Open  app/src/main/res/values/strings.xml  and change site_url to YOUR site address (keep https:// and the / at the end).
3. Wait for "Gradle sync" to finish (first time it downloads things; allow it). If it offers an "Update"/"Upgrade" for the Android Gradle plugin, say yes.
4. Build the APK:  Build > Build Bundle(s) / APK(s) > Build APK(s). When done, click "locate" in the popup. The file is app/build/outputs/apk/debug/app-debug.apk
   Or press the green Run button with a phone (USB debugging) or an emulator.
5. First use: Settings > Wi-Fi in Tsukiyo OS asks for Location (Android requires it to list networks). Tap Allow, then Scan again.

What changes in the phone UI when it runs inside this app: real Wi-Fi list, real SIM state (the Phone app opens its dialer when a SIM is in), real battery.
