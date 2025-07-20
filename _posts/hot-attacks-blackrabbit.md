---
title: "'Smash-and-Grab' Ransomware: Encrypting Files in Under 60 Seconds"
date: 2025-07-19
category: hot-attacks
excerpt: "A new ransomware family, nicknamed 'BlackRabbit,' is gaining notoriety for its incredible speed, capable of encrypting an entire corporate network in minutes, not hours."
---
In the fast-evolving landscape of ransomware, speed is a critical factor. A new family, dubbed "BlackRabbit" by researchers, is setting a terrifying new standard. Written in the highly efficient Rust programming language, BlackRabbit is designed for one purpose: maximum speed and destruction. Traditional ransomware can take hours to fully encrypt a network, giving security teams a window to detect and respond. BlackRabbit reduces that window to mere minutes.

#### The Need for Speed
The malware leverages multi-threading to an unprecedented degree, spawning a separate encryption process for each available CPU core. Its most innovative and dangerous feature, however, is its use of "intermittent encryption." Instead of encrypting entire files, it encrypts only small, strategic chunks of each file. This has two major benefits for the attacker: it's incredibly fast, and it can bypass many behavioral-based antivirus and EDR solutions that look for sustained, heavy disk I/O activity. The files are rendered completely unusable, but the encryption process looks like normal system activity. This "smash-and-grab" tactic leaves victims with virtually no time to pull the plug before their entire network is crippled.
