const fs=require("node:fs"); const vm=require("node:vm");
const text=fs.readFileSync(process.argv[2],"utf8");
const start=text.indexOf("const QUESTOES_SEED = ["); const end=text.indexOf("/* ================= estado ================= */",start);
if(start<0 || end<0) throw Error("Dataset original não encontrado");
const block=text.slice(start,end);
process.stdout.write(vm.runInNewContext(block+"\nJSON.stringify(QUESTOES_SEED)"));
