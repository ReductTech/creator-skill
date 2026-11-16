import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(new URL('../../player-preview/package.json',import.meta.url));
let parse;
function parser(){
 if(!parse){try{({parse}=require('@babel/parser'));}catch{throw Error('Missing @babel/parser. Install this Skill dependency with: npm --prefix "'+fileURLToPath(new URL('../../player-preview',import.meta.url))+'" ci --no-audit --no-fund');}}
 return parse;
}
export const ATTRIBUTE='shuku-edit-id';
export const parseSource = source => parser()(source, {sourceType:'unambiguous',plugins:['typescript','jsx'],errorRecovery:false});
const nativeTags = new Set((
  'a abbr address area article aside audio b bdi bdo blockquote br button canvas caption cite code col colgroup data datalist dd del details dfn dialog div dl dt em fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hgroup hr i iframe img input ins kbd label legend li main map mark menu meter nav noscript object ol optgroup option output p picture pre progress q rp rt ruby s samp search section select small source span strong sub summary sup table tbody td template textarea tfoot th thead time tr track u ul var video wbr ' +
  'svg animate animateMotion animateTransform circle clipPath defs desc ellipse feBlend feColorMatrix feComponentTransfer feComposite feConvolveMatrix feDiffuseLighting feDisplacementMap feDistantLight feDropShadow feFlood feFuncA feFuncB feFuncG feFuncR feGaussianBlur feImage feMerge feMergeNode feMorphology feOffset fePointLight feSpecularLighting feSpotLight feTile feTurbulence filter foreignObject g image line linearGradient marker mask metadata mpath path pattern polygon polyline radialGradient rect set stop switch symbol text textPath tspan use view'
).split(/\s+/));

export const reviewedFiles = {
  'style.json': '275336eccd51777c6db3cec0a20656612fd5c850e3ab576b1ea5ffef2aaf5e4b',
  'react/index.ts': '56870299afe3c8d2bb9a17c3f58f19065f7c8f1aff89c984db51708d75775574',
  'react/typography/index.ts': '1004765ed611a2862d322c76552accd4fc862ede97b8bb08ca7798b6ada69d55',
  'react/typography/Typography.tsx': '6faecb7a1fe9162d02286a2ee66dc815379c6b05ff4998aadcb08360e54fc44e',
  'react/layout/ContentBlock.tsx': '30e8b663fe123805991d9cee270eecdbc23cc3e1ee84a807fcffdae6a33032a8',
};
const reviewedNames = new Set(['Typography', 'ContentBlock']);
function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  if (node.type) visit(node);
  for (const [key, value] of Object.entries(node)) {
    if (['loc', 'start', 'end', 'extra', 'tokens', 'comments'].includes(key)) continue;
    if (Array.isArray(value)) for (const child of value) walk(child, visit);
    else if (value && typeof value === 'object') walk(value, visit);
  }
}
function openings(ast) {
  const nodes = [];
  walk(ast, node => { if (node.type === 'JSXOpeningElement') nodes.push(node); });
  return nodes;
}
function existingAttribute(node) {
  return node.attributes.some(a => a.type === 'JSXAttribute' && a.name.type === 'JSXIdentifier' && a.name.name === ATTRIBUTE);
}
function literal(value) {
  if (value?.type === 'JSXExpressionContainer') value = value.expression;
  return value?.type === 'StringLiteral' ? value.value : undefined;
}
function patternNames(node, result) {
  if (!node) return;
  if (node.type === 'Identifier') result.add(node.name);
  else if (node.type === 'ObjectPattern') for (const p of node.properties) patternNames(p.type === 'RestElement' ? p.argument : p.value, result);
  else if (node.type === 'ArrayPattern') for (const p of node.elements) patternNames(p, result);
  else if (node.type === 'AssignmentPattern') patternNames(node.left, result);
  else if (node.type === 'RestElement') patternNames(node.argument, result);
  else if (node.type === 'TSParameterProperty') patternNames(node.parameter, result);
}
function reviewedAliases(ast, trustedStyle) {
  if (!trustedStyle) return new Map();
  const imports = new Map(), shadowed = new Set();
  walk(ast, node => {
    if (node.type === 'ImportDeclaration' && node.importKind !== 'type' && node.source.value === '@shuku/course-style/react') {
      for (const spec of node.specifiers) if (spec.type === 'ImportSpecifier' && spec.importKind !== 'type' && reviewedNames.has(spec.imported.name)) imports.set(spec.local.name, spec.imported.name);
    }
    if (node.type === 'VariableDeclarator') patternNames(node.id, shadowed);
    if (['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression', 'ObjectMethod', 'ClassMethod', 'ClassPrivateMethod'].includes(node.type)) {
      if (node.id) patternNames(node.id, shadowed);
      for (const p of node.params) patternNames(p, shadowed);
    }
    if (node.type === 'ClassDeclaration') patternNames(node.id, shadowed);
    if (node.type === 'CatchClause') patternNames(node.param, shadowed);
  });
  for (const name of shadowed) imports.delete(name);
  return imports;
}
function cleanAST(value) {
  if (Array.isArray(value)) return value.map(cleanAST);
  if (!value || typeof value !== 'object') return value;
  const result = {};
  for (const [key, item] of Object.entries(value)) {
    if (['start', 'end', 'loc', 'extra'].includes(key)) continue;
    result[key] = cleanAST(item);
  }
  return result;
}
function annotation(source, ast, trustedStyle, reserved) {
  const originalNodes = openings(ast), aliases = reviewedAliases(ast, trustedStyle);
  const edits = [], skipped = {}, kept = originalNodes.filter(existingAttribute).length;
  const skip = reason => { skipped[reason] = (skipped[reason] || 0) + 1; };
  if (/[@]jsx(?:ImportSource|Runtime)?\b/.test(source)) return {source, edits, skipped: {'jsx-pragma': originalNodes.length}, kept};
  for (let index = 0; index < originalNodes.length; index++) {
    const node = originalNodes[index];
    if (existingAttribute(node)) continue;
    if (node.name.type !== 'JSXIdentifier') { skip('namespace-or-member-component'); continue; }
    const name = node.name.name;
    if (!nativeTags.has(name) && !aliases.has(name)) { skip('unreviewed-tag'); continue; }
    if (node.attributes.some(a => a.type === 'JSXSpreadAttribute')) { skip('spread-props'); continue; }
    if (aliases.get(name) === 'Typography') {
      const as = node.attributes.find(a => a.type === 'JSXAttribute' && a.name.name === 'as');
      if (as && !nativeTags.has(literal(as.value))) { skip('dynamic-or-custom-as'); continue; }
    }
    let id; do { id = 'e-' + crypto.randomUUID(); } while (reserved.has(id));
    reserved.add(id);
    edits.push({index, at: node.name.end, text: ` ${ATTRIBUTE}="${id}"`, id, tag: name, line: node.loc.start.line});
  }
  if (!edits.length) return {source, edits, skipped, kept};
  let changed = source;
  for (const edit of [...edits].sort((a, b) => b.at - a.at)) changed = changed.slice(0, edit.at) + edit.text + changed.slice(edit.at);
  const after = parseSource(changed), afterNodes = openings(after);
  if (afterNodes.length !== originalNodes.length) throw Error('JSX node count changed; refusing file');
  for (const edit of edits) {
    const inserted = afterNodes[edit.index].attributes[0];
    if (inserted?.type !== 'JSXAttribute' || inserted.name.name !== ATTRIBUTE || inserted.value?.type !== 'StringLiteral' || inserted.value.value !== edit.id) throw Error('Inserted attribute does not match plan; refusing file');
    afterNodes[edit.index].attributes.shift();
  }
  if (JSON.stringify(cleanAST(ast)) !== JSON.stringify(cleanAST(after))) throw Error('AST differs beyond added IDs; refusing file');
  // Independent textual check: removing precisely our insertions must recover
  // every original character, including comments, BOM and line endings.
  let delta = 0;
  const insertedRanges = [...edits].sort((a, b) => a.at - b.at).map(edit => {
    const at = edit.at + delta; delta += edit.text.length; return {...edit, at};
  });
  let recovered = changed;
  for (const edit of insertedRanges.reverse()) {
    if (recovered.slice(edit.at, edit.at + edit.text.length) !== edit.text) throw Error('Insertion range mismatch; refusing file');
    recovered = recovered.slice(0, edit.at) + recovered.slice(edit.at + edit.text.length);
  }
  if (recovered !== source) throw Error('Original source was not preserved; refusing file');
  return {source: changed, edits, skipped, kept};
}

export function addEditIds(source,{trustedStyle=false,reserved=new Set()}={}){const ast=parseSource(source);for(const n of openings(ast))for(const a of n.attributes)if(a.type==='JSXAttribute'&&a.name.name===ATTRIBUTE){const value=literal(a.value);if(value!==undefined)reserved.add(value);}return annotation(source,ast,trustedStyle,reserved);}
