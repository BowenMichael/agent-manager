# Implementation Plan: Issue #20 - Scaffold Expo Application

## 1. Architecture Overview
The goal is to initialize a cross-platform (iOS, Android, Web) Expo application in the `/apps/mobile` directory using Expo SDK 51+ and TypeScript. The application will serve as the mobile/web client for the Agent Manager control plane. It will utilize Expo Router for file-based routing and styling will be tailored to match the dark-mode aesthetic of the existing desktop dashboard. The application will be configured to connect to the backend via environment variables.

## 2. Target Files
- `apps/mobile/app.json`: Expo configuration, including web support and SDK version.
- `apps/mobile/package.json`: Project dependencies (Expo, React Native, Expo Router, TypeScript).
- `apps/mobile/tsconfig.json`: TypeScript configuration.
- `apps/mobile/babel.config.js`: Babel configuration for Expo Router.
- `apps/mobile/app/_layout.tsx`: Root layout for Expo Router, implementing the dark theme context.
- `apps/mobile/app/index.tsx`: Sessions list screen (default route).
- `apps/mobile/app/session/[id].tsx`: Session detail screen.
- `apps/mobile/app/settings.tsx`: Settings screen.
- `apps/mobile/constants/Theme.ts`: Dark mode color palette and theme definitions.
- `apps/mobile/.env`: Environment variables template (`EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_WS_URL`).
- `CHANGELOG.md`: Repository changelog.

## 3. Step-by-Step Implementation Guide
1. **Initialize Expo Project**:
   - Create the `apps` directory if it doesn't exist.
   - Run `npx create-expo-app apps/mobile --template expo-template-blank-typescript` to initialize the project with TypeScript.
   - Upgrade to Expo SDK 51+ if necessary and install Expo Router dependencies (`npx expo install expo-router react-native-safe-area-context react-native-screens expo-linking expo-constants expo-status-bar`).
2. **Configure Expo Router**:
   - Update `app.json` to configure the scheme and enable web support (`"web": { "bundler": "metro" }`).
   - Update `package.json` `main` entry point to `expo-router/entry`.
3. **Implement Theming & UI Scaffold**:
   - Create `constants/Theme.ts` defining the dark mode color palette (backgrounds, text, accents) aligned with the desktop dashboard.
   - Implement `app/_layout.tsx` to wrap the application in a `ThemeProvider` (or custom context) applying the dark theme, using Stack or Tabs for navigation.
4. **Create Base Screens**:
   - `app/index.tsx`: Basic placeholder for the Sessions list.
   - `app/session/[id].tsx`: Basic placeholder for Session details.
   - `app/settings.tsx`: Basic placeholder for Settings.
5. **Environment Configuration**:
   - Create a `.env` file (and `.env.example`) defining `EXPO_PUBLIC_API_URL` and `EXPO_PUBLIC_WS_URL`.
   - Verify environment variables are accessible in the code via `process.env`.
6. **Update Changelog**:
   - Add an entry in `CHANGELOG.md` under `[Unreleased]` for Issue #20.

## 4. Verification & Testing Criteria
- **Web Build**: Run `npm run web` (or `npx expo start --web`) in `apps/mobile` and verify the app loads in the browser without errors. Redirect output to log per user rules.
- **Routing**: Verify navigation between the Sessions list, Session detail, and Settings screens works correctly.
- **Theming**: Verify the app visually applies the dark theme configuration on all screens.
- **Environment Variables**: Ensure `EXPO_PUBLIC_API_URL` is correctly picked up by the build system.
- **Linting/Type Checking**: Run `npx tsc --noEmit` in `apps/mobile` to ensure no TypeScript compilation errors, suppressing output per rules.

## 5. Updating CHANGELOG.md under [Unreleased]
- Append a bullet point detailing the initialization of the Expo mobile app workspace, the setup of Expo Router, and the configuration of cross-platform support.
