/* Dependency-free smoke tests for the bundled Lovelace card. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../../custom_components/terramaster/www/terramaster-card.js'),'utf8');
const registered = new Map();
class HTMLElement { attachShadow(){const elements=new Map();this.shadowRoot={innerHTML:'',querySelectorAll:()=>[],getElementById:(id)=>{if(!elements.has(id))elements.set(id,{addEventListener(){},textContent:'',disabled:false});return elements.get(id);}};return this.shadowRoot;} }
const context={HTMLElement,customElements:{get:k=>registered.get(k),define:(k,v)=>registered.set(k,v)},window:{customCards:[]}};
vm.runInNewContext(source,context,{filename:'terramaster-card.js'});
const Card=registered.get('terramaster-card');
assert.ok(Card,'custom element registered');
assert.equal(context.window.customCards.length,1);
const card=new Card();
card.setConfig({entity_prefix:'sensor.my_nas'});
card.hass={states:{'sensor.my_nas_cpu_usage':{state:'22',attributes:{friendly_name:'CPU'}},'sensor.other_cpu_usage':{state:'90',attributes:{}}}};
assert.match(card.shadowRoot.innerHTML,/22/);
assert.doesNotMatch(card.shadowRoot.innerHTML,/90/);
assert.equal(card.getCardSize(),6);
assert.equal(Card.getStubConfig().type,'custom:terramaster-card');
console.log('TerraMaster card smoke tests passed');

const { test } = require('node:test');

function createCard(config = {}) {
  const instance = new Card();
  instance.setConfig(config);
  return instance;
}

test('details are collapsed initially and retain expanded state', () => {
  const instance = createCard({entity_prefix:'sensor.my_nas'});
  instance.hass={states:{
    'sensor.my_nas_disk_1_state':{state:'healthy',attributes:{friendly_name:'Disk 1'}},
    'sensor.my_nas_cpu_usage':{state:'22',attributes:{}}
  }};
  assert.match(instance.shadowRoot.innerHTML, /<details class="accordion"/);
  assert.doesNotMatch(instance.shadowRoot.innerHTML, /data-section="Disques et SMART" open/);
  instance.shadowRoot.querySelectorAll=()=>[{dataset:{section:'Disques et SMART'}}];
  instance.hass={states:{
    'sensor.my_nas_disk_1_state':{state:'healthy',attributes:{friendly_name:'Disk 1'}},
    'sensor.my_nas_cpu_usage':{state:'25',attributes:{}}
  }};
  assert.match(instance.shadowRoot.innerHTML, /data-section="Disques et SMART" open/);
});

test('escapes malicious entity values and clamps progress bars', () => {
  const instance=createCard({entity_prefix:'sensor.my_nas'});
  instance.hass={states:{
    'sensor.my_nas_cpu_usage':{state:'150',attributes:{}},
    'sensor.my_nas_model':{state:'<img src=x onerror=alert(1)>',attributes:{}}
  }};
  assert.match(instance.shadowRoot.innerHTML, /width:100%/);
  assert.doesNotMatch(instance.shadowRoot.innerHTML, /<img src=x/);
  assert.match(instance.shadowRoot.innerHTML, /&lt;img/);
});

test('share link is requested only on click and navigates to signed path', async () => {
  const instance=createCard({entry_id:'nas-entry'});
  let request;
  instance.hass={states:{},callWS:async (data)=>{
    request=data;
    return {service_response:{url:'/api/terramaster/share?entry_id=nas-entry&authSig=abc'}};
  }};
  const tab={location:{assign(url){tab.target=url;}},close(){tab.closed=true;}};
  context.window.open=()=>tab;
  context.window.location={origin:'https://ha.example'};
  context.URL=URL;
  await instance.openShares();
  assert.equal(request.domain,'terramaster');
  assert.equal(request.service,'get_share_link');
  assert.equal(request.return_response,true);
  assert.equal(request.service_data.entry_id,'nas-entry');
  assert.equal(tab.target,'https://ha.example/api/terramaster/share?entry_id=nas-entry&authSig=abc');
});

test('invalid signed link is rejected and popup is closed', async () => {
  const instance=createCard();
  instance.hass={states:{},callWS:async()=>({url:'https://untrusted.example/steal'})};
  const tab={close(){tab.closed=true;}};
  context.window.open=()=>tab;
  await instance.openShares();
  assert.equal(tab.closed,true);
  assert.match(instance.shadowRoot.getElementById('error').textContent,/invalide/);
});

test('Sections dashboard uses full-width grid options', () => {
  const instance=createCard();
  assert.deepEqual(JSON.parse(JSON.stringify(instance.getGridOptions())),{columns:'full',min_columns:6,rows:'auto'});
});

test('registry discovers French entity IDs using stable unique IDs and isolates NAS entries', async () => {
  const instance=createCard({entry_id:'nas-one'});
  const states={
    'sensor.studio_nas_nico_utilisation_processeur':{state:'23',attributes:{}},
    'sensor.disk_sdb_etat':{state:'healthy',attributes:{friendly_name:'Disk sdb'}},
    'sensor.network_eth0_debit_entrant':{state:'12',attributes:{}},
    'sensor.other_nas_cpu':{state:'99',attributes:{}}
  };
  const entries=[
    {entity_id:'sensor.studio_nas_nico_utilisation_processeur',platform:'terramaster',config_entry_id:'nas-one',unique_id:'nas.local:9222_cpu_usage'},
    {entity_id:'sensor.disk_sdb_etat',platform:'terramaster',config_entry_id:'nas-one',unique_id:'nas.local:9222_disk_sdb_state'},
    {entity_id:'sensor.network_eth0_debit_entrant',platform:'terramaster',config_entry_id:'nas-one',unique_id:'nas.local:9222_network_eth0_received_rate'},
    {entity_id:'sensor.other_nas_cpu',platform:'terramaster',config_entry_id:'nas-two',unique_id:'other_cpu_usage'}
  ];
  instance.hass={states,callWS:async req=>req.type==='config/entity_registry/list'?entries:[]};
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(instance.shadowRoot.innerHTML,/>23 %</);
  assert.match(instance.shadowRoot.innerHTML,/Disk sdb/);
  assert.match(instance.shadowRoot.innerHTML,/Réseau/);
  assert.doesNotMatch(instance.shadowRoot.innerHTML,/>99 %</);
});

test('formats large capacities and numeric values without excessive decimals', () => {
  const instance=createCard({entry_id:'nas-one'});
  instance._registryEntries=[
    {entity_id:'sensor.disk_sdb_capacite',unique_id:'nas_disk_sdb_size'},
    {entity_id:'sensor.network_eth0_debit_entrant',unique_id:'nas_network_eth0_receive_rate'}
  ];
  instance.hass={states:{
    'sensor.disk_sdb_capacite':{state:'1000.204886016',attributes:{friendly_name:'Disk capacity',unit_of_measurement:'GB'}},
    'sensor.network_eth0_debit_entrant':{state:'0.43456789',attributes:{friendly_name:'Incoming rate',unit_of_measurement:'Mbit/s'}}
  }};
  assert.match(instance.shadowRoot.innerHTML,/1 To/);
  assert.match(instance.shadowRoot.innerHTML,/0,43 Mbit\/s/);
  assert.doesNotMatch(instance.shadowRoot.innerHTML,/1000\.204886016/);
});
