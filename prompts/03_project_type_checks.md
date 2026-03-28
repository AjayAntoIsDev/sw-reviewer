Apply these rules based on project type.

Web apps:

- Must have a live demo.
- Valid examples include GitHub Pages, Vercel, and Netlify.
- Local hosting instructions alone are not enough.
- Reject ngrok, cloudflared, DuckDNS, and Render links.

Executable desktop apps:

- Must have downloadable binaries in GitHub Releases.
- Accept formats such as .exe, .app, .deb, or similar.
- Must include instructions for how to run the app properly.

Android apps:

- Must provide a .apk in GitHub Releases or a Google Play Store listing.

iOS apps:

- Must provide TestFlight access.
- If the developer lacks the Apple developer account, the note about Hack Club's team account is advisory, not a review exception.

APIs:

- Must be testable through something like Swagger or an equivalent interactive endpoint explorer.
- Must have a detailed README.

Games:

- Must be available as a web build or similar playable distribution.
- Accept platforms like itch.io or GitHub Releases.

Bots:

- Must be hosted and online for testing.
- Shipwright should never host the bot themselves.
- The demo link should point to the relevant server or channel.
- Proper command documentation is required.

Libraries:

- Must be published on a valid package manager such as npm or PyPI.
- GitHub Releases alone are not enough.
- Must explain installation and usage.
- A demo is optional but strongly preferred.
- Best case: there is already a demo project showing the library in use.

Extensions:

- Should be published in the relevant store when possible.
- A .crx or similar installable package is acceptable if store publishing is unavailable.

Userscripts:

- Must be published on Tampermonkey or GreasyFork.
- A plain text file on GitHub is not enough.

Hardware:

- Accept completed PCBs or schematics if tracked with Hackatime or Lapse.
- Accept a lapse of soldering PCBs or a circuit based on the schematic.
- Do not accept breadboard-only lapse footage.
- Do not accept hardware simulations unless the project is firmware-only for something like an ESP32.
- If the project is virtual only, a walkthrough demo is acceptable.
- If a physical version exists, require a video showing it being used and how it works.
- If physically built, firmware is required.
- If physically built, a schematic is not required.

Esolangs:

- A playground is preferred.
- Otherwise, detailed installation instructions and a syntax guide are acceptable.

CLI tools:

- Should ship as an executable file with setup and usage instructions.

VR:

- Demo video is not allowed.
- Flag for review by the designated human reviewers.

AI or ML projects:

- Do not accept Hugging Face as the submission host.
- The project should be hosted in a way that reflects normal deployment and teaches real hosting.

Game mods:

- Prefer platforms like Modrinth or CurseForge.
- Avoid GitHub Releases as the primary distribution path.
