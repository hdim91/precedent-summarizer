const assert = require('node:assert/strict');
const {splitByRanges} = require('../src/precedent_summarizer/web/static/app.js');
assert.deepEqual(splitByRanges('가😀나다',[{start:1,end:3}]),[
  {text:'가',highlight:false,start:0,end:1},
  {text:'😀나',highlight:true,start:1,end:3},
  {text:'다',highlight:false,start:3,end:4}
]);
assert.deepEqual(splitByRanges('abcdef',[{start:3,end:5},{start:1,end:4},{start:5,end:6}]),[
  {text:'a',highlight:false,start:0,end:1},{text:'bcdef',highlight:true,start:1,end:6}
]);
const source='<script>alert(1)</script>\n【이 유】\n원문  그대로😀';
for (const ranges of [[], [{start:null,end:null}], [{start:-1,end:3}], [{start:0,end:999}],
                      [{start:2,end:2}], [{start:0,end:8}], [{start:1,end:3},{start:2,end:6}]]) {
  assert.equal(splitByRanges(source,ranges).map(p=>p.text).join(''),source);
}
assert.deepEqual(splitByRanges('',[]),[]);
console.log('splitByRanges: Unicode, overlap, invalid offsets and original preservation passed');

const {minimapPositions} = require('../src/precedent_summarizer/web/static/app.js');
assert.deepEqual(minimapPositions('가😀나다', [{start:1,end:3}]), [{index:0,number:1,start:1,end:3,percent:25}]);
assert.deepEqual(minimapPositions('abcd', [{start:0,end:1},{start:null,end:null},{start:3,end:4}]), [
  {index:0,number:1,start:0,end:1,percent:0},{index:2,number:3,start:3,end:4,percent:75}
]);
assert.deepEqual(minimapPositions('',[{start:0,end:1}]), []);
assert.deepEqual(minimapPositions('abc',[
  {start:-1,end:1},{start:2,end:2},{start:0,end:4},{start:1.5,end:2},{start:undefined,end:2}
]), []);
// Without an explicit display order, source-order numbering is preserved.
assert.deepEqual(minimapPositions('abcdefghij', [{start:8,end:10},{start:1,end:4},{start:1,end:2}]).map(p=>[p.index,p.percent]),[[0,80],[1,10],[2,10]]);
console.log('minimapPositions: code-point proportions, invalid offsets, stable numbering passed');

const {evidenceDisplayOrder,courtDigestSections} = require('../src/precedent_summarizer/web/static/app.js');
const summary={facts:{},lower_court:{},disposition:{},rulings:[{}],cited_statutes:[{}],cited_precedents:[{}],separate_opinions:[{}]};
const evidence=[
 {path:'facts.evidence[0]',start:0,end:1},
 {path:'lower_court.evidence[0]',start:1,end:2},
 {path:'disposition.evidence[1]',start:2,end:3},
 {path:'disposition.evidence[0]',start:3,end:4},
 {path:'rulings[0].evidence[0]',start:4,end:5},
 {path:'cited_statutes[0].evidence[0]',start:5,end:6},
 {path:'cited_precedents[0].evidence[0]',start:6,end:7},
 {path:'separate_opinions[0].evidence[0]',start:7,end:8}
];
const order=evidenceDisplayOrder(summary,evidence);
assert.deepEqual(order,[3,2,4,0,1,5,6,7]);
const dots=minimapPositions('abcdefghij',evidence,order);
assert.deepEqual(dots.map(p=>[p.index,p.number]),[[3,1],[2,2],[4,3],[0,4],[1,5],[5,6],[6,7],[7,8]]);
assert.equal(evidence[dots[0].index].path,'disposition.evidence[0]');
const missing=evidence.map((r,i)=>i===3?{...r,start:null,end:null}:r);
assert.deepEqual(minimapPositions('abcdefghij',missing,order).map(p=>p.number),[2,3,4,5,6,7,8]);
assert.deepEqual(evidenceDisplayOrder({facts:{}},evidence),[0]);
assert.deepEqual(evidenceDisplayOrder({},evidence),[]);
assert.deepEqual(courtDigestSections({holdings_clean:'  원문 그대로  ',official_summary_clean:'요지'}),[
 {field:'holdings_clean',title:'판시사항',text:'  원문 그대로  '},
 {field:'official_summary_clean',title:'판결요지',text:'요지'}
]);
assert.deepEqual(courtDigestSections({holdings_clean:'  ',official_summary_clean:null}),[]);
assert.equal(courtDigestSections({official_summary_clean:'법원 요지'})[0].field,'official_summary_clean');
console.log('display order: conclusion first, matching map numbers; court digest fallback passed');
