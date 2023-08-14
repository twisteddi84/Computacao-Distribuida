
const musicList = document.getElementById('music-list');

function addMusicToList(name, id,filename,band) {
  var h = document.getElementById("NAME_");
  var h1 = document.getElementById("ID_");
  var h2 = document.getElementById("BAND_");
  var h3 = document.getElementById("SOUND_")

  h.textContent = `FileName: ${name}\n`;
  h1.textContent = `ID: ${id}\n`;
  h2.textContent = `Song: ${filename}\n`;
  h3.textContent = `Band: ${band}\n`;
}

const form = document.querySelector('form');
form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const formData = new FormData(form);
  const response = await fetch('http://localhost:5000/music', {
    method: 'POST',
    body: formData
  });

  const data = await response.json();
  addMusicToList(formData.get('audio').name, data.music_id,data.name,data.band);
  form.reset();
});

const listMusicBtn = document.getElementById('list-music-btn');
      listMusicBtn.addEventListener('click', async () => {
        const response = await fetch('http://localhost:5000/music');
        const data = await response.text();
        musicList.innerHTML = data;
      });


