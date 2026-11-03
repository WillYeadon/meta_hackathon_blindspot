import asyncio
import json
import pytest
import httpx
from blindspot.config import Settings
from blindspot.meta import parse_result, MetaClient, ModelError, build_request


@pytest.mark.parametrize("raw", [
    '{"valid":"false","confidence":0.9,"reason":"x"}',
    '{"valid":false,"confidence":NaN,"reason":"x"}',
    '{"valid":false,"confidence":1.1,"reason":"x"}',
    '{"valid":false,"confidence":true,"reason":"x"}',
    '{"valid":false,"valid":true,"confidence":0.9,"reason":"x"}',
    '{"valid":false,"confidence":0.9}', 'No verdict',
    '{"valid":false,"confidence":0.9,"reason":""}'
])
def test_invalid_verdicts_are_never_coerced(raw):
    with pytest.raises(ValueError):
        parse_result(raw)


def test_json_and_fences():
    assert parse_result('```json\n{"valid":false,"confidence":0.9,"reason":"Sign error."}\n```')["valid"] is False
    assert parse_result('{"probability_percent":92,"reason":"Likely."}',True)["probability_percent"]==92
    for value in (-1,101,True):
        with pytest.raises(ValueError):
            parse_result(json.dumps(dict(probability_percent=value,reason="x")),True)


def test_official_http_contract_and_no_secret_in_result():
    async def scenario():
        seen=[]
        def handler(request):
            seen.append(request)
            assert str(request.url)=="https://api.meta.ai/v1/chat/completions"
            assert request.headers["authorization"]=="Bearer TEST_ONLY"
            body=json.loads(request.content)
            assert body["model"]=="muse-spark-1.3" and body["n"]==1
            assert "max_completion_tokens" in body and "max_output_tokens" not in body
            assert body["response_format"]["type"]=="json_schema"
            return httpx.Response(200,json={"id":"test", "model":"muse-spark-1.3", "choices":[{"finish_reason":"stop","message":{"content":'{"valid":false,"confidence":0.85,"reason":"Incorrect coefficient."}'}}]})
        settings=Settings(api_key="TEST_ONLY")
        client=MetaClient(settings,transport=httpx.MockTransport(handler))
        result=await client.complete(build_request(settings,[{"role":"user","content":"x"}],False,0.8))
        assert result["valid"] is False and "TEST_ONLY" not in json.dumps(result)
        assert len(seen)==1
        await client.close()
    asyncio.run(scenario())


def test_truncated_response_is_a_failure():
    async def scenario():
        def handler(request):
            return httpx.Response(200,json={"choices":[{"finish_reason":"length","message":{"content":'{"valid":true,"confidence":1,"reason":"x"}'}}]})
        settings=Settings(api_key="TEST_ONLY"); c=MetaClient(settings,transport=httpx.MockTransport(handler))
        with pytest.raises(ModelError):
            await c.complete(build_request(settings,[],False,1))
        await c.close()
    asyncio.run(scenario())
