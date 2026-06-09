const http=require("http"),fs=require("fs"),path=require("path");
const ROOT="/Users/varundeshpande/Documents/WorldCupBeaut/public";
const TYPES={".html":"text/html",".json":"application/json",".js":"text/javascript"};
http.createServer((req,res)=>{
  let p=decodeURIComponent(req.url.split("?")[0]);
  if(p==="/")p="/sweepstake.html";
  const fp=path.join(ROOT,p);
  fs.readFile(fp,(e,d)=>{
    if(e){res.writeHead(404);res.end("404");return;}
    res.writeHead(200,{"Content-Type":TYPES[path.extname(fp)]||"text/plain"});
    res.end(d);
  });
}).listen(process.env.PORT||8777,()=>console.log("up on "+(process.env.PORT||8777)));
