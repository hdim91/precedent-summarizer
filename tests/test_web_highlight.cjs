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
