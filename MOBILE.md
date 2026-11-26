# Helvítis Veðrið – farsímaforrit

Verkefnið notar Capacitor til að pakka núverandi `static/` viðmóti sem iOS- og Android-forriti. FastAPI-bakendinn heldur áfram að keyra á Railway.

## Android – smíða APK án Mac

Það er nú GitHub Actions-verkflæði sem smíðar Android-prófunarútgáfu sjálfkrafa þegar viðeigandi skrám er breytt á `main).

Til að ræsa smíðina handvirkt:
1. Opnaðu **Actions** flipann í GitHub-verkefninu.
2. Veldu **Build Android APK**.
3. Smelltu á **Run workflow**.
4. Þegar keyrslan klárast skaltu opna hana og sækja skrána undir **Artifacts**, sem heitir `helvitis-vedrid-android-debug`.
5. Pakkaðu ZIP-skránni út og settu `app-debug.apk` upp á Android-símann.

Þetta er debug/prófunarútgáfa, ekki enn útgáfa sem er tilbúin fyrir Google Play.

## Android – staðbundin þróun í Windows

### Forsendur
- Node.js 20 eða nýrra
- Android Studio og Android SDK
- Java 21 (Android Studio getur einnig sett upp JDK fyrir Gradle)

### Uppsetning
Í möppu verkefnisins:
```bash
npm install
npx cap add android
npx cap sync android
npx cap open android
```

Android Studio opnar þá Android-verkefnið. Þar er hægt að keyra appið á tengdum síma með USB debugging eða Android hermi.

Til að smíða APK úr skipanalínu:
```bash
cd android
./gradlew assembleDebug
```
Á Windows PowerShell notarðu:
```powershell
cd android
.\gradlew.bat assembleDebug
```
APK-skráin verður í `android/app/build/outputs/apk/debug/app-debug.apk`.

## iOS – Mac

Forsendur:
- Node.js 20 eða nýrra
- Xcode á macOS

Uppsetning:
```bash
npm install
npx cap add ios
npx cap sync ios
npx cap open ios
```

## Uppfæra forritið

Eftir breytingar á `static/` eða öðrum vefskrám:
```bash
npx cap sync
```

Forritið notar sama FastAPI API og vefútgáfan á Railway. Í innbyggðu appi er API-umferð beint á framleiðsluþjóninn; í vefútgáfu helst API-slóðin hlutfallsleg við núverandi lén.

Athugið: iOS- og Android-verkefnismöppur verða búnar til með `npx cap add` á þróunarvél eða í sjálfvirku smíðaferli. Þær eru ekki geymdar í GitHub enn sem komið er.
