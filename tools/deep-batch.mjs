// Cross-language validation driver: all format work uses the public MoonBit bridge.
import fs from 'node:fs';
import { load,query,transform } from '../_build/js/release/build/cmd/bridge/bridge.js';
const tasks=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const results=[];
for(const task of tasks){
  try{
    const data=task.input?fs.readFileSync(task.input):new Uint8Array();
    const options=JSON.stringify(task.options);
    if(task.output){
      const bytes=transform(data,options);
      fs.writeFileSync(task.output,bytes,{flag:'wx'});
      results.push({ok:true,bytes:bytes.length});
    } else results.push({ok:true,result:JSON.parse(query(load(data,'{}'),options))});
  }catch(error){results.push({ok:false,error:String(error.message??error)});}
}
fs.writeFileSync(process.argv[3],JSON.stringify(results,null,2)+'\n',{flag:'wx'});
