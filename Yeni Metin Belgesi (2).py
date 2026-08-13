import os
import json
import base64
import gc
import shutil
import requests
import fitz
import ipywidgets as widgets

from ftfy import fix_text
from google.colab import output
from IPython.display import display, HTML

CHUNK_DIR = "/content/lazybook_chunks"
BOOK_STATE = {
    "prepared": False,
    "file_name": "",
    "page_count": 0,
    "chunk_count": 0,
    "pages_per_chunk": 5,
    "chunk_word_counts": [],
    "total_words": 0,
}

def encode_payload(data):
    raw = json.dumps(
        data,
        ensure_ascii=False
    )
    return base64.b64encode(
        raw.encode("utf-8")
    ).decode("utf-8")

def clean_text(text):
    text = fix_text(text or "")
    text = text.replace("\x00", "")
    text = text.replace("\r", "\n")
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()
def count_words(text):
    return len(
        str(text).split()
    )

def get_uploaded_pdf(upload_widget):
    value = upload_widget.value
    if not value:
        return None, None

    if isinstance(value, (tuple, list)):
        item = value[0]
        pdf_name = item.get("name")
        content = item.get("content")
        return pdf_name, content

    if isinstance(value, dict):
        item = list(value.values())[0]
        if isinstance(item, dict):
            name = item.get("name")
            if not name and "metadata" in item:
                name = item["metadata"].get("name")
            return name, item.get("content")
    return None, None
def prepare_pdf_from_bytes(content, pdf_name):
    global BOOK_STATE
    if os.path.exists(CHUNK_DIR):
        shutil.rmtree(CHUNK_DIR)
    os.makedirs(CHUNK_DIR, exist_ok=True)
    pdf_path = f"/content/{pdf_name}"
    with open(pdf_path, "wb") as f:
        f.write(content)

    print("PDF açılıyor:", pdf_name)

    doc = fitz.open(pdf_path)

    page_count = len(doc)


    if page_count < 100:
        pages_per_chunk = 4
    elif page_count < 300:
        pages_per_chunk = 5
    else:
      pages_per_chunk = 6

    chunk_word_counts = []
    total_words = 0
    current_pages = []

    chunk_index = 0

    print("Toplam sayfa:", page_count)

    print("Kitap hazırlanıyor...")

    for page_index in range(page_count):
        try:
            page = doc.load_page(page_index)

            text = clean_text(
                page.get_text("text")
            )

            block = (
                f"\n[Page {page_index+1}]\n{text}"
            )

            current_pages.append(block)

            if len(current_pages) >= pages_per_chunk:
              chunk_text = "\n".join(current_pages)
              wc = count_words(chunk_text)
              with open(
                  f"{CHUNK_DIR}/chunk_{chunk_index}.txt",
                  "w",
                  encoding="utf-8"
              ) as f:
                  f.write(chunk_text)
                  chunk_word_counts.append(wc)
                  total_words += wc
                  chunk_index += 1
                  current_pages = []
              percent = round(
                  (page_index + 1) / page_count * 100
              )

              print(
                  f"%{percent} hazırlandı - chunk {chunk_index}"
              )
              gc.collect()
        except Exception as e: # Corrected indentation
            print(f"Sayfa okunamadı: {page_index+1}")
            print(e)

    # Handle any remaining pages in the last chunk
    if current_pages:
        chunk_text = "\n".join(current_pages)
        wc = count_words(chunk_text)
        with open(
            f"{CHUNK_DIR}/chunk_{chunk_index}.txt",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(chunk_text)
        chunk_word_counts.append(wc)
        total_words += wc
        chunk_index += 1

    doc.close()
    gc.collect()

    BOOK_STATE = {
        "prepared": True,
        "file_name": pdf_name,
        "page_count": page_count,
        "chunk_count": chunk_index,
        "pages_per_chunk": pages_per_chunk,
        "chunk_word_counts": chunk_word_counts,
        "total_words": total_words,
    }

    print("=========================================")
    print("✅ KİTAP HAZIR")
    print("=========================================")
    print("Dosya:", pdf_name)
    print("Sayfa:", page_count)
    print("Chunk:", chunk_index)
    print("Kelime:", total_words)

def prepare_pdf_from_url(pdf_url):

    print("PDF indiriliyor...")

    response = requests.get(
        pdf_url,
        stream=True
    )

    if response.status_code != 200:

        print("PDF indirilemedi")
        return

    pdf_name = "browser_book.pdf"

    pdf_path = f"/content/{pdf_name}"

    with open(pdf_path, "wb") as f:

        for chunk in response.iter_content(1024 * 1024):

            if chunk:
                f.write(chunk)

    print("İndirme tamamlandı")

    with open(pdf_path, "rb") as f:

        content = f.read()

    prepare_pdf_from_bytes(
        content,
        pdf_name
    )

def get_meta_payload():
    if not BOOK_STATE["prepared"]:
        return encode_payload({
            "ok": False
        })
    return encode_payload({
        "ok": True,
        "file_name":
            BOOK_STATE["file_name"],
        "chunk_count":
            BOOK_STATE["chunk_count"],
        "pages_per_chunk":
            BOOK_STATE["pages_per_chunk"],
        "chunk_word_counts":
            BOOK_STATE["chunk_word_counts"],
        "total_words":
            BOOK_STATE["total_words"],
        "mode":
            "DISK CHUNK MODE",
    })
def get_chunk_payload(index):
    if not BOOK_STATE["prepared"]:
        return encode_payload({
            "ok": False
        })
    index = int(index)
    path = f"{CHUNK_DIR}/chunk_{index}.txt"
    if not os.path.exists(path):
        return encode_payload({
            "ok": False
        })
    with open(path, "r", encoding="utf-8") as f:

        text = f.read()

    start_page = (
        index * BOOK_STATE["pages_per_chunk"]
    ) + 1

    end_page = min(
        BOOK_STATE["page_count"],
        start_page + BOOK_STATE["pages_per_chunk"] - 1
    )

    return encode_payload({

        "ok": True,

        "text": text,
        "page_start": start_page,
        "page_end": end_page,
    })


def prepare_from_url(url):

    prepare_pdf_from_url(url)

    return "ok"


output.register_callback(
    "lazybook.get_meta_payload",
    get_meta_payload
)
output.register_callback(
    "lazybook.get_chunk_payload",
    get_chunk_payload
)
output.register_callback(
    "lazybook.prepare_from_url",
    prepare_from_url
)
upload = widgets.FileUpload(
    accept=".pdf",
    multiple=False,
    description="📚 PDF Seç"
)

prepare_button = widgets.Button(
    description="⚡ Kitabı Hazırla",
    button_style="success"
)

prepare_output = widgets.Output()

def prepare_clicked(btn):

    with prepare_output:

        prepare_output.clear_output()

        pdf_name, content = get_uploaded_pdf(upload)
        if not pdf_name:

            print("Önce PDF seç.")

            return

        try:

            prepare_pdf_from_bytes(
                content,
                pdf_name
            )
        except Exception as e:

            print("Hazırlama hatası:")
            print(e)

prepare_button.on_click(
    prepare_clicked
)

display(
    upload,
    prepare_button,
    prepare_output
)
html = r"""

<style>

body{
  background:#0f0f0f;
}

.main-wrapper{
  display:flex;
  gap:28px;
  align-items:flex-start;
  font-family:Arial,sans-serif;
  margin-top:20px;
}

.player{
  width:430px;
  background:#181818;
  padding:22px;
  border-radius:18px;
  color:white;
  box-shadow:0 14px 36px rgba(0,0,0,0.35);
  position:sticky;
  top:8px;
}

.reader-shell{
  width:1020px;
}

.controls-grid{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:8px;
  margin-top:14px;
}

.controls-grid button,
.main-btn{
  padding:11px 12px;
  border:none;
  border-radius:10px;
  cursor:pointer;
  background:#2a2a2a;
  color:white;
  font-size:14px;
}

.controls-grid button:hover,
.main-btn:hover{
  background:#ff4d6d;
}

.main-btn{
  width:100%;
  margin-bottom:10px;
}

.text-panel{
  width:100%;
  min-height:650px;
  max-height:760px;
  overflow-y:auto;
  background:linear-gradient(
    180deg,
    #ff0000 0%,
    #ffff00 100%
  );
  padding:26px;
  border-radius:24px;
  box-sizing:border-box;
}

.page-grid{
  display:grid;
  grid-template-columns:
    repeat(2,minmax(0,1fr));
  gap:26px;
}

.word{
  padding:1px 2px;
  border-radius:4px;
}

.highlight{
  background:#ffffff;
  color:#EA4335;
}

.status-box{
  margin-top:14px;
  padding:12px;
  border-radius:12px;
  background:#202020;
  color:#d8d8d8;
  font-size:13px;
  line-height:1.8;
}

.page-card{
  min-height:600px;
  background:linear-gradient(
    180deg,
    #FBBC04 0%,
    #EA4335 100%
  );
  border-radius:14px;
  padding:32px;
  color:#1967D2;
}

.page-content{
  font-family:Georgia,"Times New Roman",serif;
  line-height:2;
  font-size:18px;
  text-align:justify;
}

.page-label{
  text-align:right;
  font-size:12px;
  font-weight:700;
  color:#6d5a46;
  margin-bottom:20px;
}

.track{
  width:100%;
  height:12px;
  background:#2e2e2e;
  border-radius:999px;
  overflow:hidden;
  margin-top:10px;
}

.fill{
  width:0%;
  height:100%;
  background:linear-gradient(
    90deg,
    #60a5fa,
    #34d399
  );
  transition:width 0.25s ease;
}

.pct{
  margin-top:8px;
  font-size:12px;
}

.range{
  width:100%;
}

.lang-select{
  width:100%;
  margin-top:8px;
  padding:10px;
  border-radius:10px;
  background:#2a2a2a;
  color:white;
  border:none;
}
.url-input{
  width:100%;
  padding:12px;
  border-radius:10px;
  border:none;
  margin-top:8px;
  background:#2a2a2a;
  color:white;
  box-sizing:border-box;
}

@media(max-width:1100px){

  .main-wrapper{
    flex-direction:column;
  }

  .player,
  .reader-shell{
    width:100%;
  }

  .page-grid{
    grid-template-columns:1fr;
  }
}

</style>

<div class="main-wrapper">

<div class="player">

<div style="
font-size:22px;
font-weight:700;
margin-bottom:12px;
">
🎧 Sesli Kitap
</div>

<div style="
font-size:13px;
color:#b8b8b8;
margin-bottom:14px;
">
700+ sayfa stabil sürüm
</div>

<button
class="main-btn"
onclick="syncBook()"
>
📚 Hazırlanan kitabı bağla
</button>

<div style="margin-top:16px;">
<b>PDF Linki</b>
</div>

<input
id="pdfUrl"
class="url-input"
type="text"
placeholder="PDF linki yapıştır"
/>

<button
class="main-btn"
onclick="prepareFromUrl()"
style="margin-top:10px;"
>
🌐 Linkten Hazırla
</button>

<div class="controls-grid">

<button onclick="playAudio()">
▶️ Play
</button>

<button onclick="pauseAudio()">
⏸ Pause
</button>

<button onclick="resumeAudio()">
🔁 Resume
</button>

<button onclick="stopAudio()">
⏹ Stop
</button>

<button onclick="prevChunk()">
⏮ Prev
</button>

<button onclick="nextChunk()">
⏭ Next
</button>

</div>
<div class="status-box">

<div>
<b>Hazırlık durumu:</b>
</div>

<div id="preparedText">
Kontrol edilmedi
</div>

<div style="margin-top:12px;">
<b>Bağlantı durumu:</b>
</div>

<div id="bindingText">
Bağlanmadı
</div>

<div style="margin-top:12px;">
<b>Bağlantı ilerlemesi:</b>
</div>

<div class="track">
<div
id="bindingFill"
class="fill">
</div>
</div>

<div
id="bindingPct"
class="pct">
0%
</div>

<div
id="bindingStep"
class="pct">
Henüz başlamadı
</div>

</div>

<div class="status-box">

<div>
<b>Dosya:</b>
<span id="metaFile">-</span>
</div>

<div>
<b>Toplam sayfa:</b>
<span id="metaPages">-</span>
</div>

<div>
<b>Toplam chunk:</b>
<span id="metaChunks">-</span>
</div>

<div>
<b>Toplam kelime:</b>
<span id="metaWords">-</span>
</div>

<div>
<b>Aktif bölüm:</b>
<span id="activeChunk">-</span>
</div>

</div>

<br>

<div>
<b>Dil</b>
</div>

<select
id="langSelect"
class="lang-select"
>

<option value="tr-TR">
Türkçe
</option>

<option value="en-US">
English
</option>

</select>

<br><br>

<div>Hız</div>

<input
id="rateSlider"
class="range"
type="range"
min="0.5"
max="2"
step="0.1"
value="1"
/>

<div id="rateText">1.0x</div>

<br>

<div>Ses</div>
<input
id="volumeSlider"
class="range"
type="range"
min="0"
max="1"
step="0.1"
value="1"
/>

<div id="volumeText">100%</div>

</div>

<div class="reader-shell">

<div
class="text-panel"
id="textPanel"
>

Metin burada görünecek.

</div>

</div>

</div>

<script>

let meta = null;

let currentChunkIndex = 0;

let currentChunkText = "";

let utterance = null;

let currentRate = 1;

let currentVolume = 1;

const textPanel =
  document.getElementById("textPanel");

const bindingFill =
  document.getElementById("bindingFill");

const bindingPct =
  document.getElementById("bindingPct");

const bindingStep =
  document.getElementById("bindingStep");

document
.getElementById("rateSlider")
.addEventListener("input", function(){

  currentRate =
    parseFloat(this.value);

  document
  .getElementById("rateText")
  .innerText =
    currentRate.toFixed(1) + "x";
});

document
.getElementById("volumeSlider")
.addEventListener("input", function(){

  currentVolume =
    parseFloat(this.value);

  document
  .getElementById("volumeText")
  .innerText =
    Math.round(currentVolume * 100) + "%";
});

function setProgress(value,text){

  bindingFill.style.width =
    value + "%";

  bindingPct.innerText =
    value + "%";

  bindingStep.innerText =
    text;
}

function decodePayload(raw){

  raw = String(raw).trim();

  if(
    (raw.startsWith('"') &&
    raw.endsWith('"')) ||

    (raw.startsWith("'") &&
    raw.endsWith("'"))
  ){
    raw = raw.slice(1,-1);
  }

  const binary = atob(raw);

  const bytes =
    Uint8Array.from(
      binary,
      c => c.charCodeAt(0)
    );

  const text =
    new TextDecoder().decode(bytes);

  return JSON.parse(text);
}
async function invoke(name,args=[]){

  const res =
    await google.colab.kernel.invokeFunction(
      name,
      args,
      {}
    );

  let raw = null;

  if(
    res &&
    res.data &&
    typeof res.data["text/plain"] === "string"
  ){
    raw = res.data["text/plain"];
  }

  if(!raw){
    throw new Error(
      "Python callback cevabı alınamadı."
    );
  }

  return decodePayload(raw);
}

async function prepareFromUrl(){

  const url =
    document.getElementById("pdfUrl").value;

  if(!url){

    alert("PDF linki gir.");

    return;
  }

  try{

    alert("PDF indiriliyor...");

    await google.colab.kernel.invokeFunction(
      "lazybook.prepare_from_url",
      [url],
      {}
    );

    alert("PDF hazırlandı.");

  }catch(err){

    console.error(err);

    alert("Hata oluştu.");
  }
}

async function syncBook(){

  try{

    stopAudio();

    setProgress(
      10,
      "Metadata alınıyor"
    );

    document
    .getElementById("bindingText")
    .innerText =
      "Bağlanıyor...";

    meta =
      await invoke(
        "lazybook.get_meta_payload"
      );

    if(!meta.ok){

      document
      .getElementById("preparedText")
      .innerText =
        "Hazır değil";

      document
      .getElementById("bindingText")
      .innerText =
        "Bağlanmadı";

      setProgress(
        100,
        "Önce kitabı hazırla"
      );

      alert(
        "Önce kitabı hazırla."
      );

      return;
    }

    document
    .getElementById("preparedText")
    .innerText =
      "Hazır ✅";

    setProgress(
      40,
      "Metadata işlendi"
    );

    document
    .getElementById("metaFile")
    .innerText =
      meta.file_name;

    document
    .getElementById("metaPages")
    .innerText =
      meta.page_count;

    document
    .getElementById("metaChunks")
    .innerText =
      meta.chunk_count;

    document
    .getElementById("metaWords")
    .innerText =
      meta.total_words;

    setProgress(
      70,
      "İlk chunk yükleniyor"
    );

    await loadChunk(0);

    setProgress(
      100,
      "Bağlantı tamamlandı"
    );

    document
    .getElementById("bindingText")
    .innerText =
      "Bağlandı ✅";
}catch(err){

    console.error(err);

    document
    .getElementById("bindingText")
    .innerText =
      "Bağlantı hatası";

    setProgress(
      100,
      "Bağlantı hatası"
    );

    alert(
      "Bağlantı hatası: " + err.message
    );
  }
}

function escapeHtml(text){

  return String(text)
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;");
}

function renderChunk(text){

  const pages =
    String(text).split(/[\[]Page \d+[\]]/g);

  let pageNumber = 1;

  let wordId = 0;

  let html = "";

  pages.forEach(p=>{

    p = p.trim();

    if(!p) return;

    const words =
      p.split(/\s+/);

    const rendered =
      words.map(w=>{

        return `
        <span
        class="word"
        id="w${wordId++}">
        ${escapeHtml(w)}
        </span>
        `;

      }).join(" ");

    html += `
      <div class="page-card">

        <div class="page-label">
        𐌔𐌀𐌙𐌅𐌀 ${pageNumber}
        </div>

        <div class="page-content">
        ${rendered}
        </div>

      </div>
    `;

    pageNumber++;

  });

  return `
    <div class="page-grid">
    ${html}
    </div>
  `;
}

async function loadChunk(index){

  if(!meta) return;

  if(index < 0) return;

  if(index >= meta.chunk_count)
    return;

  const data =
    await invoke(
      "lazybook.get_chunk_payload",
      [index]
    );

  if(!data.ok) return;

  currentChunkIndex = index;

  currentChunkText = data.text;

  textPanel.innerHTML =
    renderChunk(currentChunkText);

  document
  .getElementById("activeChunk")
  .innerText =
    (currentChunkIndex + 1)
    + " / "
    + meta.chunk_count;
}

function highlightWord(charIndex){

  const words =
    currentChunkText.split(/\s+/);

  let total = 0;

  let target = 0;

  for(let i=0;i<words.length;i++){

    total +=
      words[i].length + 1;

    if(charIndex < total){

      target = i;

      break;
    }
  }

  document
  .querySelectorAll(".word")
  .forEach(el=>{

    el.classList.remove("highlight");

  });

  const active =
    document.getElementById("w"+target);

  if(active){

    active.classList.add("highlight");
  }
}

function speakCurrentChunk(){

  if(!currentChunkText){

    alert("Önce kitabı bağla.");

    return;
  }


  utterance =
    new SpeechSynthesisUtterance(
      currentChunkText
    );

  utterance.rate =
    currentRate;

  utterance.volume =
    currentVolume;

  utterance.lang =
    document.getElementById("langSelect").value;

  utterance.onboundary =
    function(e){

      if(
        typeof e.charIndex === "number"
      ){

        highlightWord(
          e.charIndex
        );
      }
  };
utterance.onend =
    async function(){

      if(
        meta &&
        currentChunkIndex < meta.chunk_count - 1
      ){

        await loadChunk(
          currentChunkIndex + 1
        );

        speakCurrentChunk();
      }
  };

  speechSynthesis.speak(
    utterance
  );
}

function playAudio(){

  stopAudio();

  speakCurrentChunk();
}

function pauseAudio(){

  speechSynthesis.pause();
}

function resumeAudio(){

  speechSynthesis.resume();
}

function stopAudio(){

  speechSynthesis.cancel();
}

async function nextChunk(){

  stopAudio();

  await loadChunk(
    currentChunkIndex + 1
  );
}

async function prevChunk(){

  stopAudio();

  await loadChunk(
    currentChunkIndex - 1
  );
}

</script>
"""

display(HTML(html))