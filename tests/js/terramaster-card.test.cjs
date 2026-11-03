/* Dependency-free smoke tests for the bundled Lovelace card. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../../custom_components/terramaster/www/terramaster-card.js'),'utf8');
const registered = new Map();
class HTMLElement { attachShadow(){this.shadowRoot={innerHTML:'',getElementById:()=>({addEventListener(){},textContent:'',disabled:false})};return this.shadowRoot;} }
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
