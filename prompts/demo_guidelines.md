# Demo Validation Guidelines

Rules for what constitutes a valid demo link or artifact per project type. Used by the checks agent for the `demo_validity` check. These rules validate the link type and accessibility only — actual demo testing is for human reviewers.

## Web apps
- **Valid**: Live URL on GitHub Pages, Vercel, Netlify, or similar static/serverless hosting
- **Reject**: ngrok, cloudflared, DuckDNS, Render links
- **Reject**: localhost URLs or local-only instructions without a live deployment

## Desktop apps (executables)
- **Valid**: `.exe`, `.app`, `.deb`, `.dmg`, `.AppImage`, or similar binaries in GitHub Releases
- **Reject**: Source-only with no prebuilt binary

## Android apps
- **Valid**: `.apk` in GitHub Releases OR a Google Play Store listing
- **Reject**: Source-only with no APK or store listing

## iOS apps
- **Valid**: TestFlight link
- **Note**: If the developer lacks an Apple Developer account, this is not a review exception

## APIs
- **Valid**: Swagger UI, interactive endpoint explorer, or documented live base URL
- **Reject**: No testable endpoint or documentation-only with no live API

## Games
- **Valid**: Web build (playable in browser), itch.io page, or GitHub Releases with downloadable build
- **Reject**: Source-only with no playable or downloadable build

## Bots (Discord, Telegram, etc.)
- **Valid**: Bot is hosted and online, with a link to the relevant server or channel
- **Reject**: Bot requires the reviewer to host it themselves

## Libraries / packages
- **Valid**: Published on npm, PyPI, crates.io, Maven Central, or equivalent package manager
- **Reject**: GitHub Releases as the only distribution — libraries must be on a real package manager
- **Preferred**: A demo project or playground showing the library in use

## Browser extensions
- **Valid**: Published in the Chrome Web Store, Firefox Add-ons, or equivalent store
- **Acceptable**: `.crx` or `.xpi` installable package if store publishing is unavailable

## Userscripts
- **Valid**: Published on Tampermonkey (GreasyFork) or similar userscript repository
- **Reject**: Plain `.js` file on GitHub with no userscript platform listing

## Hardware projects
- **Valid**: Completed PCB or schematic with fabrication files, video of the physical build in use
- **Reject**: Breadboard-only footage, hardware simulations (unless firmware-only for ESP32 or similar)
- **Note**: If physically built, firmware is required; schematic is not required

## CLI tools
- **Valid**: Executable binary or installable package with setup and usage instructions
- **Acceptable**: Install-from-source instructions if clearly documented

## VR projects
- **Action**: Always flag for human review — do not attempt automated demo validation
- **Reject**: Demo video alone is not acceptable

## AI / ML projects
- **Reject**: Hugging Face as the submission host
- **Valid**: Self-hosted deployment, cloud-hosted API, or packaged application

## Game mods
- **Preferred**: Modrinth, CurseForge, or equivalent mod platform
- **Discouraged**: GitHub Releases as the primary distribution path

## Esolangs
- **Preferred**: Interactive playground or web REPL
- **Acceptable**: Detailed installation instructions with syntax guide
