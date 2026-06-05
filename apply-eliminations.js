#!/usr/bin/env node
/* apply-eliminations.js — regenerate public/board.json from the sealed draw + a list
 * of officially-eliminated countries. Deterministic: the tracker routine decides WHO
 * is out (from 2+ sources); this script does the JSON surgery and preserves prior dates.
 *
 * Usage:
 *   node apply-eliminations.js --out "Scotland,Curaçao,Haiti"        # cumulative list of ALL eliminated teams
 *   node apply-eliminations.js --out "..." --champion "Brazil"       # crown the winner at the end
 *   node apply-eliminations.js --out "..." --date 2026-06-18         # override "knocked out" date (default: today)
 *
 * Country names must match draw-private.json / GROUPS exactly (e.g. "Bosnia & Herzegovina", "Curaçao").
 */
const fs=require("fs"), path=require("path");
const ROOT=__dirname;
const DRAW=path.join(ROOT,"draw-private.json");
const BOARD=path.join(ROOT,"public","board.json");

function arg(flag){ const i=process.argv.indexOf(flag); return i>=0?process.argv[i+1]:null; }

if(!fs.existsSync(DRAW)){ console.error("Missing draw-private.json at repo root. Export it once from the admin tool."); process.exit(1); }
const draw=JSON.parse(fs.readFileSync(DRAW,"utf8"));
const mapping=draw.mapping||{};
const validCountries=new Set(Object.keys(mapping));
// flag lookup from draw.groups ({A:[["Mexico","🇲🇽"],...],...})
const flags={};
for(const g of Object.keys(draw.groups||{})) for(const [name,flag] of draw.groups[g]) flags[name]=flag;
const flagOf=c=>flags[c]||"";

const outList=(arg("--out")||"").split(",").map(s=>s.trim()).filter(Boolean);
const champion=arg("--champion")||null;
const date=arg("--date")||new Date().toLocaleDateString("en-GB",{day:"2-digit",month:"short"});

// validate
const bad=outList.filter(c=>!validCountries.has(c));
if(bad.length){ console.error("Unknown country name(s) — fix spelling to match the draw exactly:\n  "+bad.join("\n  ")); process.exit(1); }
if(champion && !validCountries.has(champion)){ console.error("Unknown champion: "+champion); process.exit(1); }

// preserve prior knockout dates so they don't all jump to today on each run
let prev={out:{},log:[]};
if(fs.existsSync(BOARD)){ try{ prev=JSON.parse(fs.readFileSync(BOARD,"utf8")); }catch(e){} }

const out={};
for(const c of outList){
  const when = (prev.out && prev.out[c] && prev.out[c].when) ? prev.out[c].when : date;
  out[c]={ person:mapping[c], when };
}
// log: newest first; keep insertion order roughly by previous log then new
const log=[];
for(const c of outList){ log.unshift({country:c, person:mapping[c], when:out[c].when, flag:flagOf(c)}); }

const revealed={};
if(champion){ revealed[champion]=mapping[champion]; }

const board={
  drawn:true, readonly:true, mapping:null,
  out, revealed,
  bracket: prev.bracket||null,   // bracket left to admin / future tracker pass
  log,
  champion: champion||null,
  exportedAt:new Date().toISOString()
};
fs.writeFileSync(BOARD, JSON.stringify(board,null,2));
console.log(`Wrote public/board.json — ${outList.length} eliminated${champion?`, champion ${champion}`:""}.`);
