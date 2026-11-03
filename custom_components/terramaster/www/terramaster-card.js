/* TerraMaster dashboard — bundled with the integration, no external dependencies. */
const STYLES = `
:host{display:block;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Arial,sans-serif)}
ha-card{overflow:hidden;padding:20px;background:var(--ha-card-background,var(--card-background-color));border-radius:18px}
.header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.title{font-size:22px;font-weight:700}.subtitle{font-size:12px;color:var(--secondary-text-color);margin-top:4px}
.status{font-size:12px;border-radius:99px;padding:6px 12px;background:color-mix(in srgb,var(--success-color,#43a047) 15%,transparent);color:var(--success-color,#43a047)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.tile{border:1px solid var(--divider-color);border-radius:12px;padding:14px;min-width:0}
.label{font-size:12px;color:var(--secondary-text-color);margin-bottom:9px}.value{font-size:21px;font-weight:650;overflow-wrap:anywhere}
.meter{height:7px;border-radius:8px;background:var(--divider-color);overflow:hidden;margin-top:12px}
.fill{height:100%;background:var(--primary-color);border-radius:8px;transition:width .25s}
.section{font-size:15px;font-weight:650}.accordion{margin-top:12px;border:1px solid var(--divider-color);border-radius:12px;padding:12px}.accordion summary{cursor:pointer}.rows{display:grid;gap:8px;margin-top:12px}
.item{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:11px 13px;border:1px solid var(--divider-color);border-radius:10px}
.item small{display:block;color:var(--secondary-text-color);margin-top:3px}.item span:last-child{text-align:right;overflow-wrap:normal;white-space:nowrap;flex-shrink:0}.item>div{min-width:0;overflow-wrap:anywhere}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}
button{border:0;border-radius:9px;padding:11px 16px;background:var(--primary-color);color:var(--text-primary-color,#fff);cursor:pointer;font:inherit}
button:disabled{opacity:.55;cursor:wait}.error{color:var(--error-color);font-size:13px;margin-top:10px}
@media(max-width:480px){ha-card{padding:14px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.value{font-size:18px}}
`;
const esc = (s) => String(s ?? "—").replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const valid = (s) => s && !['unknown','unavailable','none'].includes(String(s.state).toLowerCase());
const pct = (s) => Math.max(0,Math.min(100,Number(s?.state)||0));
const formatReading = (state, unit='') => {
  const raw=String(state ?? '—');
  const n=Number(raw);
  if (!raw.trim() || !Number.isFinite(n)) return [raw,unit];
  const normalized=unit.trim();
  let value=n, displayUnit=unit;
  if (normalized==='GB' || normalized==='Go') {
    if (Math.abs(n)>=1000) {value=n/1000;displayUnit='To';}
    else displayUnit='Go';
  }
  return [new Intl.NumberFormat('fr-FR',{maximumFractionDigits:2}).format(value),displayUnit];
};

const formatDuration = (state) => {
  const days=Number(state);
  if (!Number.isFinite(days) || days<0) return String(state ?? '—');
  const minutes=Math.round(days*24*60);
  const d=Math.floor(minutes/1440);
  const h=Math.floor((minutes%1440)/60);
  const m=minutes%60;
  return [d?' '+d+' j':'',h?' '+h+' h':'',m?' '+m+' min':''].join('').trim() || '0 min';
};

class TerraMasterCard extends HTMLElement {
  setConfig(config) { this.config = { ...config }; if (!this.shadowRoot) this.attachShadow({mode:'open'}); this.render(); }
  set hass(hass) { this._hass=hass; if (!this._registryLoading && !this._registryEntries && typeof hass.callWS==='function') this.loadRegistry(hass); this.render(); }
  async loadRegistry(hass) {
    this._registryLoading=true;
    try {
      const [entries,devices]=await Promise.all([
        hass.callWS({type:'config/entity_registry/list'}),
        hass.callWS({type:'config/device_registry/list'})
      ]);
      const terramaster=entries.filter(e=>e.platform==='terramaster');
      const requested=this.config?.entry_id;
      const selected=requested || terramaster.find(e=>e.config_entry_id)?.config_entry_id || devices.find(d=>d.config_entries?.length && terramaster.some(e=>e.device_id===d.id))?.config_entries?.[0];
      const ownedDevices=new Set(devices.filter(d=>d.config_entries?.includes(selected)).map(d=>d.id));
      this._registryEntries=terramaster.filter(e=>selected && (e.config_entry_id===selected || (e.device_id && ownedDevices.has(e.device_id))));
    } catch(e) { this._registryError=e; }
    finally {this._registryLoading=false;this.render();}
  }
  getCardSize() { return 6; }
  getGridOptions() { return {columns:'full',min_columns:6,rows:'auto'}; }
  static getStubConfig() { return {type:'custom:terramaster-card'}; }
  entities() {
    const states=this._hass?.states||{};
    if (this._registryEntries) return this._registryEntries.filter(e=>states[e.entity_id] && e.entity_id.startsWith('sensor.')).map(e=>[e.entity_id,states[e.entity_id],e.unique_id||'']);
    const all=Object.entries(states).filter(([id])=>id.startsWith('sensor.'));
    const prefix=this.config?.entity_prefix;
    const guessed=all.find(([id])=>id.endsWith('_shared_folders_page'));
    const guessedPrefix=guessed?.[0].replace(/_shared_folders_page$/,'');
    return all.filter(([id,s])=>prefix ? id.startsWith(prefix) : (guessedPrefix ? id.startsWith(guessedPrefix+'_') : (id.includes('terramaster') || /terramaster/i.test(s.attributes?.friendly_name||'')))).map(([id,s])=>[id,s,id]);
  }
  render() {
    if (!this.shadowRoot || !this._hass) return;
    const expanded = new Set([...this.shadowRoot.querySelectorAll('details[open]')].map(node=>node.dataset.section));
    const entities=this.entities();
    const lookup=(suffix)=>entities.find(([, ,uid])=>uid.endsWith('_'+suffix))?.[1];
    const name=this.config?.title || (valid(lookup('model')) ? lookup('model').state : null) || 'TerraMaster NAS';
    const tile=(label,key,unit='',meter=false)=>{const s=lookup(key);if(!valid(s))return '';return `<div class="tile"><div class="label">${esc(label)}</div><div class="value">${esc(key==='uptime'?formatDuration(s.state):formatReading(s.state)[0])}${key==='uptime'?'':esc(unit)}</div>${meter?`<div class="meter"><div class="fill" style="width:${pct(s)}%"></div></div>`:''}</div>`;};
    const group=(label,filter)=>{const items=entities.filter(([, ,uid])=>filter(uid)).filter(([,s])=>valid(s));if(!items.length)return '';return `<details class="accordion" data-section="${esc(label)}" ${expanded.has(label)?'open':''}><summary class="section">${esc(label)} (${items.length})</summary><div class="rows">${items.map(([id,s])=>`<div class="item"><div>${esc(s.attributes?.friendly_name||id)}<small>${esc(id)}</small></div><span>${esc(/_disk_/.test(id) && /durée de fonctionnement|power.on|operating.time|runtime/i.test(s.attributes?.friendly_name||id) && ['d','j','days'].includes(s.attributes?.unit_of_measurement) ? formatDuration(s.state) : formatReading(s.state,s.attributes?.unit_of_measurement||'').join(' '))</span></div>`).join('')}</div></details>`;};
    const html=`<style>${STYLES}</style><ha-card><div class="header"><div><div class="title">${esc(name)}</div><div class="subtitle">TOS ${esc(lookup('tos_version')?.state)} · ${esc(lookup('cpu_model')?.state)}</div></div><div class="status">${entities.length?'● Connecté':'● Aucune entité détectée'}</div></div>
    <div class="grid">${tile('CPU','cpu_usage',' %',true)}${tile('Mémoire','memory_usage',' %',true)}${tile('Température','temperature',' °C')}${tile('Stockage','disk_usage',' %',true)}${tile('Disponibilité','uptime',' j')}${tile('Partages','shared_folders_page')}</div>
    ${group('Disques et SMART',id=>/_disk_/.test(id))}${group('RAID',id=>/_raid_/.test(id))}${group('Volumes',id=>/_volume_/.test(id))}${group('Réseau',id=>/_network_/.test(id))}${group('Services',id=>/_(ssh|telnet|snmp)_service$/.test(id))}
    <div class="actions"><button id="shares">Ouvrir les partages ↗</button></div><div class="error" id="error" role="alert"></div></ha-card>`;
    this.shadowRoot.innerHTML=html;
    this.shadowRoot.getElementById('shares').addEventListener('click',()=>this.openShares());
  }
  async openShares() {
    const btn=this.shadowRoot.getElementById('shares'); const error=this.shadowRoot.getElementById('error');
    btn.disabled=true;error.textContent='';
    // Open synchronously in the user gesture to avoid popup blockers.
    const tab=window.open('about:blank','_blank');
    try {
      const service_data=this.config?.entry_id?{entry_id:this.config.entry_id}:{};
      const response=await this._hass.callWS({type:'call_service',domain:'terramaster',service:'get_share_link',service_data,return_response:true});
      const path=response?.service_response?.url||response?.response?.url||response?.url;
      if(typeof path!=='string'||!path.startsWith('/api/terramaster/share?')) throw new Error('Lien signé absent ou invalide');
      if(tab)tab.location.assign(new URL(path,window.location.origin).href);
      else error.textContent='Le navigateur bloque les fenêtres. Autorisez les popups pour Home Assistant.';
    } catch(e) {if(tab)tab.close();error.textContent=e?.message||'Impossible de générer le lien.';}
    finally {btn.disabled=false;}
  }
}
if(!customElements.get('terramaster-card'))customElements.define('terramaster-card',TerraMasterCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(c=>c.type==='terramaster-card'))window.customCards.push({type:'terramaster-card',name:'TerraMaster NAS',description:'Tableau de bord du NAS TerraMaster'});
