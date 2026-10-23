import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'

test('failed logout blocks private identity until the server confirms logout',async()=>{
  globalThis.window=new EventTarget()
  const storage=new Map()
  globalThis.localStorage={getItem:key=>storage.get(key) || null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)}
  let loggedIn=true,attempts=0
  const server=createServer((req,res)=>{
    res.setHeader('content-type','application/json')
    if(req.url.endsWith('/logout/')){
      attempts++
      if(attempts===1){res.statusCode=503;res.end(JSON.stringify({error:{code:'temporarily_unavailable',message:'暂时无法退出'}}));return}
      loggedIn=false
    }
    res.end(JSON.stringify({data:{user:loggedIn?{id:42,username:'test-coach',role:'coach',display_name:'教练'}:null,brand:{display_name:'教练',coach_name:'教练'},csrf_token:'test-token'}}))
  })
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
  const original=globalThis.fetch
  globalThis.fetch=(path,init)=>original(`http://127.0.0.1:${server.address().port}${path}`,init)
  try{
    const state=await import('../src/state/session.ts')
    await state.loadSession()
    assert.equal(state.session.value.user.id,42)
    await assert.rejects(state.logout())
    await state.loadSession()
    assert.equal(state.session.value.user,null)
    assert.equal(state.logoutPending.value,true)
    await state.logout()
    assert.equal(state.logoutPending.value,false)
    assert.equal(state.session.value.user,null)
  }finally{
    globalThis.fetch=original
    server.closeAllConnections()
    await new Promise(resolve=>server.close(resolve))
  }
})
