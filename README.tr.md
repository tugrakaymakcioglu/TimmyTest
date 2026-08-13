<div align="center">

<img src="docs/assets/banner.png" alt="TimmyTest - Sıfır Token Test Koşucusu ve AI Ajan Zekası" width="100%" />

# ⚡ TimmyTest (Türkçe)

### Sıfır-Token Test Koşucusu • AST Test Açığı Tespit Edici • AI Ajan Prompt Üreticisi

[![PyPI Version](https://img.shields.io/badge/pypi-v0.1.0-blue.svg?logo=pypi&logoColor=white)](https://pypi.org/project/timmytest/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Lisans: Apache-2.0](https://img.shields.io/badge/Lisans-Apache%202.0-green.svg)](LICENSE)
[![Testler](https://img.shields.io/badge/testler-31%20ba%C5%9Far%C4%B1l%C4%B1-brightgreen.svg?logo=pytest&logoColor=white)](tests/)
[![AI Agent Uyumlu](https://img.shields.io/badge/AI%20Agent-Claude%20%7C%20Codex%20%7C%20Cursor%20%7C%20Antigravity-orange.svg?logo=openai&logoColor=white)](#-neden-timmytest-token-t%C3%BCkenme-problemi)

[English README](README.md) &nbsp;·&nbsp; [Hızlı Başlangıç](#-h%C4%B1zl%C4%B1-ba%C5%9Flang%C4%B1%C3%A7) &nbsp;·&nbsp; [Kurulum](#-kurulum) &nbsp;·&nbsp; [Temel Özellikler](#-temel-%C3%B6zellikler) &nbsp;·&nbsp; [Desteklenen Ekosistemler](#-desteklenen-ekosistemler)

<br>

**Yapay zeka kodlama ajanlarınızın testleri keşfetmek ve çalıştırmak için on binlerce LLM token'ı yakmasını engelleyin.**  
TimmyTest projenizi yerel olarak analiz eder, testleri 0 token ile çalıştırır, eksik test modüllerini tespit eder ve Claude Code, Cursor, Codex veya Antigravity gibi ajanlara doğrudan kopyalanabilir yoğun bir teşhis prompt'u üretir.

</div>

---

## 💡 Neden TimmyTest? Token Tükenme Problemi

AI kodlama ajanları (Claude Code, OpenAI Codex, Antigravity, Cursor, Gemini CLI) bir projeyi test etmeye çalıştıklarında:
1. Dizinleri listelemek ve test ayarlarını aramak için **15.000–35.000 token** harcar.
2. Test komutlarını tahmin etmeye çalışırken hata alır ve yüzlerce satırlık ham logları tekrar tekrar okur.
3. Asıl hatayı çözmek yerine context penceresini ham traceback çıktılarıyla doldurur.

### 💰 Token Maliyet ve Verimlilik Karşılaştırması

| Aşama | Tek Başına Standart AI Ajanı | TimmyTest Yerel Ön-Uçuşu ile |
| :--- | :--- | :--- |
| **Proje & Stack Keşfi** | 💸 8.000–15.000 token | ⚡ **0 token** (Yerel AST + Yapılandırma detektörü) |
| **Eksik Testleri Bulma** | 💸 10.000–25.000 token | ⚡ **0 token** (Deterministik Test Açığı Analizörü) |
| **Test Çalıştırma & Parse**| 💸 12.000–30.000 token | ⚡ **0 token** (Yerel subprocess koşucusu) |
| **Hata Kök Neden Analizi**| 💸 5.000–18.000 token | ⚡ **0 token** (Kural tabanlı teşhis motoru) |
| **Ajanın Tükettiği Token**| ❌ **35.000–88.000+ token** | ✅ **~400–900 token** (Doğrudan Hazır Prompt Kartı) |
| **Hız ve Doğruluk** | ⚠️ Yavaş, halüsinasyona açık | 🚀 **Anlık ve %100 Deterministik** |

---

## 🚀 Kurulum

```bash
# uv ile (Önerilen)
uv tool install timmytest

# pipx ile
pipx install timmytest

# pip ile
pip install timmytest
```

---

## ⚡ Hızlı Başlangıç

```bash
# 1. Tam Proje Denetimi (Tara + Çalıştır + Açıkları Bul + Prompt Üret)
timmytest check .
# (Prompt otomatik olarak panoya kopyalanır!)

# 2. Hızlı Statik Açık Taraması (Testleri çalıştırmaz)
timmytest scan /path/to/project

# 3. Sadece Hataları Teşhis Et
timmytest run --only-failures

# 4. AI Ajanı İçin Optimize Edilmiş Prompt Al
timmytest prompt --copy
```

---

## 📦 Desteklenen Ekosistemler

- **Python:** `pytest`, `unittest`
- **TypeScript / JavaScript:** `vitest`, `jest`, `mocha`, `playwright`, `npm test`
- **Rust:** `cargo test`
- **Go:** `go test ./...`
- **Özel:** `--cmd` ile belirtilen herhangi bir komut

---

## 📄 Lisans

Apache-2.0 Lisansı. Detaylar için [LICENSE](LICENSE) dosyasına bakın.
