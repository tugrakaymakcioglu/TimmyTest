<div align="center">

<img src="docs/assets/banner.png" alt="TimmyTest - Sıfır Token Test Koşucusu ve AI Ajan Zekası" width="100%" />

# ⚡ TimmyTest (Türkçe)

### Sıfır-Token Test Koşucusu • AST Test Açığı Tespit Edici • AI Ajan Prompt Üreticisi • MCP Sunucusu

[![PyPI Version](https://img.shields.io/badge/pypi-v1.2.0-blue.svg?logo=pypi&logoColor=white)](https://pypi.org/project/timmytest/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Lisans: Apache-2.0](https://img.shields.io/badge/Lisans-Apache%202.0-green.svg)](LICENSE)
[![Testler](https://img.shields.io/badge/testler-59%20ba%C5%9Far%C4%B1l%C4%B1-brightgreen.svg?logo=pytest&logoColor=white)](tests/)
[![MCP Sunucusu](https://img.shields.io/badge/MCP-Protokol%20Hazır-purple.svg?logo=json&logoColor=white)](#-model-context-protocol-mcp-sunucusu)
[![AI Agent Uyumlu](https://img.shields.io/badge/AI%20Agent-Claude%20%7C%20Cursor%20%7C%20Copilot%20%7C%20Antigravity-orange.svg?logo=openai&logoColor=white)](#-neden-timmytest-token-t%C3%BCkenme-problemi)

[English README](README.md) &nbsp;·&nbsp; [Hızlı Başlangıç](#-h%C4%B1zl%C4%B1-ba%C5%9Flang%C4%B1%C3%A7) &nbsp;·&nbsp; [Tek Komutla Kurulum](#-tek-komutla-an%C4%B1nda-proje-entegrasyonu) &nbsp;·&nbsp; [MCP Sunucusu](#-model-context-protocol-mcp-sunucusu) &nbsp;·&nbsp; [Kurulum](#-kurulum)

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

## ⚡ Tek Komutla Anında Proje Entegrasyonu

AI kodlama ajanlarınızın (Cursor, Claude Code, Copilot, Antigravity, Aider) sıfır token harcayarak testleri yönetmesi için projenizin kök dizininde tek bir komut çalıştırmanız yeterlidir:

```bash
# Proje kök dizininde:
timmytest integrate
# veya kuruluma gerek kalmadan uvx ile:
uvx timmytest integrate
```

**Bu komut projenize otomatik olarak şunları ekler:**
- `.cursorrules` & `.cursor/rules/timmytest.mdc` (Cursor IDE kural dosyaları)
- `CLAUDE.md` (Claude Code CLI talimatları)
- `.github/copilot-instructions.md` (GitHub Copilot kuralları)
- `AGENTS.md` (Antigravity, Devin, Codex, Aider için evrensel kurallar)
- `.timmytest.yml` (Özel yapılandırma ve yoksayma ayarları)
- `.cursor/mcp.json` (Doğrudan MCP Sunucu entegrasyonu)

---

## 🚀 Kurulum

```bash
# uv ile (Önerilen - Çok Hızlı)
uv tool install timmytest

# pipx ile
pipx install timmytest

# pip ile
pip install timmytest

# Sıfır Kurulumla Çalıştırma (uvx)
uvx timmytest check
```

---

## ⚡ Hızlı Başlangıç

### 🎮 Tam Ekran Uygulama

TimmyTest'i argümansız çalıştırdığınızda tuşlarla yönetilen tam ekran bir terminal uygulaması açılır:

```bash
timmytest
```

Akış: pixel-art açılış ekranı ve beyaz yükleme çubuğu → sistem gereksinimleri ve dosya bütünlüğü kontrolü
→ dil seçimi (Türkçe / English) → son ayarlar → çalışma alanı oluşturma (proje adı, kullanılan AI ajan
şirketleri, dosya yolu — klasörü terminale sürükleyip bırakabilirsiniz) → canlı panel.

Panelde: geçen / kalan / atlanan / eksik test grafikleri, test hazırlık skoru, çalıştırma geçmişi,
prompt araçları, Discord raporlama, ajan entegrasyonları ve sağ üstte **ÇALIŞTIR** butonu.

```bash
timmytest ui --fresh   # tüm kurulum akışını baştan oynatır
```

Panel tuşları: `↑ ↓` gezinme · `Enter` seçim · `Tab` panel değiştir · `R` / `F5` analizi çalıştır · `Q` çıkış.
Dil, çalışma alanları, geçmiş ve Discord webhook bilgisi `~/.timmytest/state.json` içinde saklanır.

### Komutlar

```bash
# 1. Projeyi AI Ajanları İçin Yapılandır
timmytest integrate

# 2. Tam Proje Denetimi (Tara + Çalıştır + Açıkları Bul + Prompt Üret)
timmytest check .
# (Prompt otomatik olarak panoya kopyalanır!)

# 3. AI Ajanına Özel Ham Çıktı Akışı (Görsel süssüz, saf token tasarrufu)
timmytest agent .

# 4. Hızlı Statik Açık Taraması (Testleri çalıştırmaz)
timmytest scan /path/to/project

# 5. Sadece Hataları Teşhis Et ve Düzeltme Önerilerini Gör
timmytest run --only-failures
```

---

## 🔌 Model Context Protocol (MCP) Sunucusu

TimmyTest yerleşik bir **MCP Sunucusu** sunar. Claude Desktop, Cursor, Antigravity, Zed gibi MCP destekleyen tüm AI araçları TimmyTest'i doğrudan yerel bir fonksiyon/araç olarak çağırabilir:

| Araç Adı | Açıklama |
| :--- | :--- |
| `timmytest_check` | Tam sıfır-token test denetimi, açık analizi ve teşhis prompt'u üretir. |
| `timmytest_scan` | Test edilmemiş sınıfları, fonksiyonları ve eksik test dosyalarını tespit eder. |
| `timmytest_run` | Testleri çalıştırır ve kök neden analizli hata kartları döner. |
| `timmytest_prompt` | Bug fix veya test yazımı için token yoğunluklu AI prompt'u sunar. |
| `timmytest_integrate`| Projeye AI ajan kurallarını ve ayarlarını tek tıkla kurar. |

### Cursor / Claude Desktop Yapılandırması
`.cursor/mcp.json` veya `claude_desktop_config.json` dosyasına ekleyin:
```json
{
  "mcpServers": {
    "timmytest": {
      "command": "timmytest",
      "args": ["mcp"]
    }
  }
}
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
