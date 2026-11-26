# Helvítis Veðrið – farsímaforrit

Verkefnið notar Capacitor til að pakka núverandi `static/` viðmóti sem iOS- og Android-forriti. FastAPI-bakendinn heldur áfram að keyra á Railway.

## Forsendur
- Node.js 20 eða nýrra
- Xcode á macOS fyrir iOS-útgáfu
- Android Studio fyrir Android-útgáfu

## Uppsetning
```bash
npm install
npx cap add ios
npx cap add android
npx cap sync
```

## Opna forritin
```bash
npm run cap:ios
npm run cap:android
```

## Uppfæra vefviðmótið í öppunum
Eftir breytingar á `static/`:
```bash
npx cap sync
```

Forritið notar sama FastAPI API og vefútgáfan á Railway. Í innbyggðu appi er API-umferð beint á framleiðsluþjóninn; í vefútgáfu helst API-slóðin hlutfallsleg við núverandi lén.

Athugið: iOS- og Android-verkefnismöppur verða búnar til með `npx cap add` á þróunarvél. Þær eru ekki búnar til sjálfkrafa af GitHub Contents API.
