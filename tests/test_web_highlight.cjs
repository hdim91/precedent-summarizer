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
assert.deepEqual(minimapPositions('가😀나다', [{start:1,end:3}]), [{index:0,start:1,end:3,percent:25}]);
assert.deepEqual(minimapPositions('abcd', [{start:0,end:1},{start:null,end:null},{start:3,end:4}]), [
  {index:0,start:0,end:1,percent:0},{index:2,start:3,end:4,percent:75}
]);
assert.deepEqual(minimapPositions('',[{start:0,end:1}]), []);
assert.deepEqual(minimapPositions('abc',[
  {start:-1,end:1},{start:2,end:2},{start:0,end:4},{start:1.5,end:2},{start:undefined,end:2}
]), []);
// Overlapping positions are independent buttons; numbering follows API order, never sorted away.
assert.deepEqual(minimapPositions('abcdefghij', [{start:8,end:10},{start:1,end:4},{start:1,end:2}]).map(p=>[p.index,p.percent]),[[0,80],[1,10],[2,10]]);
console.log('minimapPositions: code-point proportions, invalid offsets, stable numbering passed');
