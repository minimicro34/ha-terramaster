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
