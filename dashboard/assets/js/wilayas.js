/**
 * wilayas.js — All 58 Algerian Wilayas (post-2019 administrative reform)
 * Used to populate dropdowns and charts across the MedAssist AI dashboard.
 */

const ALGERIA_WILAYAS = [
  { code: "01", name: "Adrar" },
  { code: "02", name: "Chlef" },
  { code: "03", name: "Laghouat" },
  { code: "04", name: "Oum El Bouaghi" },
  { code: "05", name: "Batna" },
  { code: "06", name: "Béjaïa" },
  { code: "07", name: "Biskra" },
  { code: "08", name: "Béchar" },
  { code: "09", name: "Blida" },
  { code: "10", name: "Bouira" },
  { code: "11", name: "Tamanrasset" },
  { code: "12", name: "Tébessa" },
  { code: "13", name: "Tlemcen" },
  { code: "14", name: "Tiaret" },
  { code: "15", name: "Tizi Ouzou" },
  { code: "16", name: "Alger" },
  { code: "17", name: "Djelfa" },
  { code: "18", name: "Jijel" },
  { code: "19", name: "Sétif" },
  { code: "20", name: "Saïda" },
  { code: "21", name: "Skikda" },
  { code: "22", name: "Sidi Bel Abbès" },
  { code: "23", name: "Annaba" },
  { code: "24", name: "Guelma" },
  { code: "25", name: "Constantine" },
  { code: "26", name: "Médéa" },
  { code: "27", name: "Mostaganem" },
  { code: "28", name: "M'Sila" },
  { code: "29", name: "Mascara" },
  { code: "30", name: "Ouargla" },
  { code: "31", name: "Oran" },
  { code: "32", name: "El Bayadh" },
  { code: "33", name: "Illizi" },
  { code: "34", name: "Bordj Bou Arréridj" },
  { code: "35", name: "Boumerdès" },
  { code: "36", name: "El Tarf" },
  { code: "37", name: "Tindouf" },
  { code: "38", name: "Tissemsilt" },
  { code: "39", name: "El Oued" },
  { code: "40", name: "Khenchela" },
  { code: "41", name: "Souk Ahras" },
  { code: "42", name: "Tipaza" },
  { code: "43", name: "Mila" },
  { code: "44", name: "Aïn Defla" },
  { code: "45", name: "Naâma" },
  { code: "46", name: "Aïn Témouchent" },
  { code: "47", name: "Ghardaïa" },
  { code: "48", name: "Relizane" },
  /* 2019 Administrative Reform — 10 new wilayas */
  { code: "49", name: "Timimoun" },
  { code: "50", name: "Bordj Badji Mokhtar" },
  { code: "51", name: "Ouled Djellal" },
  { code: "52", name: "Béni Abbès" },
  { code: "53", name: "In Salah" },
  { code: "54", name: "In Guezzam" },
  { code: "55", name: "Touggourt" },
  { code: "56", name: "Djanet" },
  { code: "57", name: "El M'Ghair" },
  { code: "58", name: "El Meniaa" }
];

/**
 * Populate a <select> element with all 58 wilayas.
 * @param {string|HTMLSelectElement} selectOrId - element or its ID
 * @param {string} [selectedCode] - pre-select this code if provided
 */
function populateWilayaSelect(selectOrId, selectedCode = "") {
  const el = typeof selectOrId === "string"
    ? document.getElementById(selectOrId)
    : selectOrId;
  if (!el) return;

  // Keep blank placeholder if present
  const placeholder = el.querySelector('option[value=""]');
  el.innerHTML = "";
  if (placeholder) el.appendChild(placeholder);

  ALGERIA_WILAYAS.forEach(({ code, name }) => {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = `${code} - ${name}`;
    if (code === selectedCode) opt.selected = true;
    el.appendChild(opt);
  });
}

/**
 * Get a wilaya display name from its code.
 * @param {string} code - e.g. "16"
 * @returns {string} e.g. "16 - Alger"
 */
function getWilayaLabel(code) {
  const w = ALGERIA_WILAYAS.find(w => w.code === String(code).padStart(2, "0") || w.code === String(code));
  return w ? `${w.code} - ${w.name}` : `Wilaya ${code}`;
}

