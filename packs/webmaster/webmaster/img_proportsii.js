// Проба пропорций картинок · Мила качества · 13.10.2026 (повод: аватар вытянут)
// Запуск: в браузере на странице (консоль, Playwright page.evaluate, DYM). Ширины 390 и 1440.
// Красное: картинка на экране искажена больше чем на 2 % и не спасена object-fit cover/contain.
(() => {
  const bad = [];
  for (const img of document.images) {
    if (!img.complete || !img.naturalWidth || !img.clientWidth || !img.clientHeight) continue;
    const fit = getComputedStyle(img).objectFit;           // fill = растягивает
    if (fit === 'cover' || fit === 'contain' || fit === 'scale-down') continue;
    const nat = img.naturalWidth / img.naturalHeight;
    const shown = img.clientWidth / img.clientHeight;
    const skew = Math.abs(shown / nat - 1);
    if (skew > 0.02) bad.push({src: img.currentSrc.slice(-80), nat: nat.toFixed(3),
      shown: shown.toFixed(3), skew: (skew * 100).toFixed(1) + '%', fit});
  }
  return {checked: document.images.length, bad};
})();
// Две судьбы для проверки пробы: <img style="width:200px;height:400px" src="квадрат"> → в bad;
// то же + object-fit:cover → не в bad. Совпали вердикты — сломана проба.
