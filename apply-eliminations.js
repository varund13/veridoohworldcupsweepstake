#!/usr/bin/env node
/* apply-eliminations.js — regenerate public/board.json from the sealed draw + a list
 * of officially-eliminated countries. Deterministic: the tracker decides WHO
 * is out (from 2+ sources); this script does the JSON surgery and preserves prior dates.
 *
 * The draw is stored encrypted (draw-private.enc). The passphrase is required at runtime:
 *   node apply-eliminations.js --pass "prism-falcon-eclipse-301" --out "Scotland,Curaçao,Haiti"
 *   node apply-eliminations.js --pass "prism-falcon-eclipse-301" --out "..." --champion "Brazil"
 *
 * Country names must match draw-private.enc / GROUPS exactly.
 */
const fs=require("fs"), path=require("path"), crypto=require("crypto");
const ROOT=__dirname;
const ENC_DRAW=path.join(ROOT,"draw-private.enc");
const BOARD=path.join(ROOT,"public","board.json");

function arg(flag){ const i=process.argv.indexOf(flag); return i>=0?process.argv[i+1]:null; }

// ---- Decrypt draw-private.enc ----
if(!fs.existsSync(ENC_DRAW)){
  console.error("Missing draw-private.enc at repo root.");
  process.exit(1);
}
const passphrase = arg("--pass") || "prism-falcon-eclipse-301";
let draw;
try {
  const enc = JSON.parse(fs.readFileSync(ENC_DRAW,"utf8"));
  const salt = Buffer.from(enc.salt,"base64");
  const iv   = Buffer.from(enc.iv,"base64");
  const tag  = Buffer.from(enc.tag,"base64");
  const ct   = Buffer.from(enc.data,"base64");
  const key  = crypto.pbkdf2Sync(passphrase, salt, 100000, 32, "sha256");
  const dec  = crypto.createDecipheriv("aes-256-gcm", key, iv);
  dec.setAuthTag(tag);
  const plain = dec.update(ct) + dec.final("utf8");
  draw = JSON.parse(plain);
} catch(e) {
  console.error("Failed to decrypt draw-private.enc — wrong passphrase or corrupt file:", e.message);
  process.exit(1);
}

const mapping=draw.mapping||{};
const validCountries=new Set(Object.keys(mapping));
const flags={};
for(const g of Object.keys(draw.groups||{})) for(const [name,flag] of draw.groups[g]) flags[name]=flag;
const flagOf=c=>flags[c]||"";

const outList=(arg("--out")||"").split(",").map(s=>s.trim()).filter(Boolean);
const champion=arg("--champion")||null;
const date=arg("--date")||new Date().toLocaleDateString("en-GB",{day:"2-digit",month:"short"});

// validate
const bad=outList.filter(c=>!validCountries.has(c));
if(bad.length){ console.error("Unknown country name(s):\n  "+bad.join("\n  ")); process.exit(1); }
if(champion && !validCountries.has(champion)){ console.error("Unknown champion: "+champion); process.exit(1); }

// preserve prior knockout dates
let prev={out:{},log:[]};
if(fs.existsSync(BOARD)){ try{ prev=JSON.parse(fs.readFileSync(BOARD,"utf8")); }catch(e){} }

const out={};
for(const c of outList){
  const when = (prev.out && prev.out[c] && prev.out[c].when) ? prev.out[c].when : date;
  out[c]={ person:mapping[c], when };
}
const log=[];
for(const c of outList){ log.unshift({country:c, person:mapping[c], when:out[c].when, flag:flagOf(c)}); }

const revealed={};
if(champion){ revealed[champion]=mapping[champion]; }

const board={
  drawn:true, readonly:true, mapping:null,
  out, revealed,
  bracket: prev.bracket||null,
  log,
  champion: champion||null,
  exportedAt:new Date().toISOString()
};
fs.writeFileSync(BOARD, JSON.stringify(board,null,2));
console.log(`Wrote public/board.json — ${outList.length} eliminated${champion?`, champion ${champion}`:""}.`);
