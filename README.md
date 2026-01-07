# Global Humanity Bot

A cross-server Discord bot that allows users to play a "Cards Against Humanity" style game globally. It features SFW/NSFW modes, automated AI players ("System Bots") to fill empty seats, and instant game backfilling.

## 🚀 Features

* **Global Matchmaking:** Players from different servers can play together seamlessly.
* **Dual Modes:**
    * **SFW (Family Friendly):** Clean cards suitable for general audiences.
    * **NSFW (Adults Only):** Restricted to Age-Restricted Discord channels.
* **System Bots:** AI players automatically fill empty slots if the queue waits longer than 3 minutes.
* **Smart Backfilling:** New players can join an active game and instantly replace a System Bot, inheriting their hand and score.
* **Render Ready:** Includes a keep-alive server for 24/7 cloud hosting.

## 🃏 Contributing New Cards

We welcome community submissions for new Black and White cards! You may submit a **Pull Request (PR)** to add cards to the game.

### How to Add Cards
1.  Open `cards.json`.
2.  Locate the appropriate category (`sfw` or `nsfw`).
3.  Add your card text to the `black_cards` (Prompts) or `white_cards` (Answers) list.
    * *Note: Black cards must use an underscore `_` for the blank space.*
4.  Submit a Pull Request with the title: `Add cards: [Your Short Description]`.

### ⚠️ Contributor License Agreement (CLA)
By submitting a Pull Request to this repository, you agree to the following:
1.  **Transfer of Rights:** You grant **Joseph Dykens** a perpetual, worldwide, exclusive, royalty-free license to use, display, and distribute the content (cards) you submitted.
2.  **Originality:** You certify that the content you are submitting is your original work and does not violate any existing copyrights.
3.  **No Ownership:** Once merged, these cards become part of the proprietary software and you waive any claim to ownership or compensation.

**Note:** Pull Requests modifying core logic (`main.py`) will be rejected and closed immediately.

## 🛠️ Installation & Setup

### Prerequisites
* Python 3.9+
* A Discord Bot Token

### Local Setup
1.  **Clone the repository.**
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment:**
    Create a `.env` file in the root folder and add your token:
    ```env
    DISCORD_TOKEN=your_token_here
    ```
4.  **Run the bot:**
    ```bash
    python main.py
    ```

## ⚖️ License & Legal Notice

**Copyright (c) 2026 Joseph Dykens. All Rights Reserved.**

This software is **Proprietary**.

* **Strict No-Copy Policy:** You may not copy, modify, distribute, or reproduce this code without prior written permission.
* **Non-Commercial:** Commercial use (including paid hosting, subscriptions, or selling the code) is strictly prohibited.
* **Limited Exception:** Users are permitted to modify `cards.json` *solely* for the purpose of submitting a Pull Request to the official repository.

**⚠️ ENFORCEMENT WARNING:**
If we discover that this code has been copied, modified, or distributed without express written permission, **we reserve the right to pursue legal action** to the fullest extent of the law.

To request permission for commercial use or distribution, please contact:
**Joseph Dykens** at [discordrosell@gmail.com](mailto:discordrosell@gmail.com)
