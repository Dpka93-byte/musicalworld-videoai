const single = document.getElementById('form-single');
const result = document.getElementById('result');
const batchBtn = document.getElementById('btn-batch');
const batchBox = document.getElementById('batch-json');
const batchResult = document.getElementById('batch-result');

if (single) {
  single.addEventListener('submit', async (e) => {
    e.preventDefault();
    result.classList.remove('hide');
    result.innerHTML = '⏳ Creating video…';
    const fd = new FormData(single);
    const res = await fetch('/create', { method: 'POST', body: fd });
    const json = await res.json();
    if (!json.ok) result.innerHTML = '❌ ' + json.error;
    else result.innerHTML = `✅ Done! <a href="/download/${json.file}">Download video</a>`;
  });
}

if (batchBtn) {
  batchBtn.addEventListener('click', async () => {
    batchResult.classList.remove('hide');
    batchResult.innerHTML = '⏳ Rendering chapters…';
    let payload;
    try { payload = JSON.parse(batchBox.value); }
    catch { batchResult.innerHTML = '❌ Invalid JSON'; return; }

    const res = await fetch('/create_batch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    const json = await res.json();
    if (!json.ok) { batchResult.innerHTML = '❌ ' + (json.error || 'Unknown error'); return; }

    const list = (json.episodes || []).map(ep => `<li>Ep ${ep.chapter}: ${ep.title} — <a href="/download/${ep.file}">${ep.file}</a></li>`).join('');
    batchResult.innerHTML = `✅ Created ${json.episodes.length} episodes<ul>${list}</ul><p><strong>Playlist text</strong> (copy for YouTube description):<pre>${json.playlist_text}</pre></p>`;
  });
}
