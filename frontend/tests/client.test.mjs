import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { api, resetRequests, setCsrfToken, ApiError } from '../src/api/client.ts'

test('identity change aborts an old response instead of exposing private data', async () => {
  let received
  const requestReceived = new Promise(resolve => { received = resolve })
  const server = createServer((req,res) => {
    received()
    setTimeout(() => { res.setHeader('content-type','application/json'); res.end(JSON.stringify({data:{student:'old user'}})) },60)
  })
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve))
  const original = globalThis.fetch
  globalThis.fetch = (path,init) => original(`http://127.0.0.1:${server.address().port}${path}`,init)
  try {
    const pending = api('/api/v1/private/')
    await requestReceived
    resetRequests()
    await assert.rejects(pending,{name:'AbortError'})
  } finally {
    globalThis.fetch = original
    server.closeAllConnections()
    await new Promise(resolve => server.close(resolve))
  }
})

test('CSRF and error fields survive a failed write', async () => {
  const original = globalThis.fetch
  let headers
  globalThis.fetch = async (_path,init) => {
    headers = new Headers(init.headers)
    return new Response(JSON.stringify({error:{code:'validation_error',message:'请检查',fields:{units:['请输入整数']}}}),{status:400,headers:{'content-type':'application/json'}})
  }
  try {
    setCsrfToken('fresh-token')
    await assert.rejects(api('/api/v1/write/',{method:'POST',body:'{}'}), err => err instanceof ApiError && err.fields.units[0]==='请输入整数')
    assert.equal(headers.get('X-CSRFToken'),'fresh-token')
  } finally { globalThis.fetch = original }
})
