---
title: "Lazarus Group's New 'DeFi Drainer' Siphons Millions from Crypto Wallets"
date: 2025-07-20
category: hot-attacks
excerpt: "The North Korean Lazarus Group has deployed a new malware strain that targets browser extensions for popular crypto wallets, draining funds by tricking users into signing malicious transactions."
---
The Lazarus Group, a notorious state-sponsored hacking collective from North Korea, has once again set its sights on the cryptocurrency world with a sophisticated new attack vector dubbed the "DeFi Drainer." This campaign moves beyond traditional malware, targeting users directly through their browser-based crypto wallets like MetaMask and Phantom.

#### The Attack Chain
The attack begins with a highly targeted spear-phishing email, often impersonating a well-known venture capital firm or a new DeFi project, inviting the target to participate in a lucrative private sale. The link leads to a professionally designed, yet completely fraudulent, web platform. When the user attempts to connect their wallet to the site, a malicious script is triggered. This script exploits a subtle UI redressing vulnerability in the wallet's transaction approval pop-up. The user sees a simple, harmless-looking request (e.g., "Sign in to this site"), but the underlying code they are actually approving is a `setApprovalForAll` transaction. This function gives the attacker's smart contract unlimited permission to withdraw all of the user's assets (NFTs, stablecoins, etc.) from their wallet. The funds are then immediately siphoned off through a series of tumblers to obscure their final destination.

#### Why It Works
This attack is devastatingly effective because it doesn't require stealing the user's private keys. It leverages social engineering and exploits the user's trust in the wallet's user interface. By the time the user realizes what has happened, their assets are long gone. This campaign highlights the increasing sophistication of crypto-focused attacks and the need for extreme vigilance when interacting with new DeFi platforms.
