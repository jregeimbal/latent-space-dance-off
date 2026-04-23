# GitHub - ollama/ollama-python: Ollama Python library · GitHub

> Source: https://github.com/ollama/ollama-python
> Cached: 2026-04-23T00:18:40.936Z

---

# Ollama Python Library

[](#ollama-python-library)
The Ollama Python library provides the easiest way to integrate Python 3.8+ projects with [Ollama](https://github.com/ollama/ollama).

## Prerequisites

[](#prerequisites)

- [Ollama](https://ollama.com/download) should be installed and running

Pull a model to use with the library: `ollama pull <model>` e.g. `ollama pull gemma3`

- See [Ollama.com](https://ollama.com/search) for more information on the models available.

## Install

[](#install)
pip install ollama
## Usage

[](#usage)
from ollama import chat
from ollama import ChatResponse

response: ChatResponse = chat(model='gemma3', messages=[
  {
    'role': 'user',
    'content': 'Why is the sky blue?',
  },
])
print(response['message']['content'])
# or access fields directly from the response object
print(response.message.content)
See [_types.py](/ollama/ollama-python/blob/main/ollama/_types.py) for more information on the response types.

## Streaming responses

[](#streaming-responses)
Response streaming can be enabled by setting `stream=True`.

from ollama import chat

stream = chat(
    model='gemma3',
    messages=[{'role': 'user', 'content': 'Why is the sky blue?'}],
    stream=True,
)

for chunk in stream:
  print(chunk['message']['content'], end='', flush=True)
## Cloud Models

[](#cloud-models)
Run larger models by offloading to Ollama’s cloud while keeping your local workflow.

- Supported models: `deepseek-v3.1:671b-cloud`, `gpt-oss:20b-cloud`, `gpt-oss:120b-cloud`, `kimi-k2:1t-cloud`, `qwen3-coder:480b-cloud`, `kimi-k2-thinking` See [Ollama Models - Cloud](https://ollama.com/search?c=cloud) for more information

### Run via local Ollama

[](#run-via-local-ollama)

- Sign in (one-time):

```
ollama signin

```

- Pull a cloud model:

```
ollama pull gpt-oss:120b-cloud

```

- Make a request:

from ollama import Client

client = Client()

messages = [
  {
    'role': 'user',
    'content': 'Why is the sky blue?',
  },
]

for part in client.chat('gpt-oss:120b-cloud', messages=messages, stream=True):
  print(part.message.content, end='', flush=True)
### Cloud API (ollama.com)

[](#cloud-api-ollamacom)
Access cloud models directly by pointing the client at `https://ollama.com`.

- Create an API key from [ollama.com](https://ollama.com/settings/keys) , then set:

```
export OLLAMA_API_KEY=your_api_key

```

- (Optional) List models available via the API:

```
curl https://ollama.com/api/tags

```

- Generate a response via the cloud API:

import os
from ollama import Client

client = Client(
    host='https://ollama.com',
    headers={'Authorization': 'Bearer ' + os.environ.get('OLLAMA_API_KEY')}
)

messages = [
  {
    'role': 'user',
    'content': 'Why is the sky blue?',
  },
]

for part in client.chat('gpt-oss:120b', messages=messages, stream=True):
  print(part.message.content, end='', flush=True)
## Custom client

[](#custom-client)
A custom client can be created by instantiating `Client` or `AsyncClient` from `ollama`.

All extra keyword arguments are passed into the [`httpx.Client`](https://www.python-httpx.org/api/#client).

from ollama import Client
client = Client(
  host='http://localhost:11434',
  headers={'x-some-header': 'some-value'}
)
response = client.chat(model='gemma3', messages=[
  {
    'role': 'user',
    'content': 'Why is the sky blue?',
  },
])
## Async client

[](#async-client)
The `AsyncClient` class is used to make asynchronous requests. It can be configured with the same fields as the `Client` class.

import asyncio
from ollama import AsyncClient

async def chat():
  message = {'role': 'user', 'content': 'Why is the sky blue?'}
  response = await AsyncClient().chat(model='gemma3', messages=[message])

asyncio.run(chat())
Setting `stream=True` modifies functions to return a Python asynchronous generator:

import asyncio
from ollama import AsyncClient

async def chat():
  message = {'role': 'user', 'content': 'Why is the sky blue?'}
  async for part in await AsyncClient().chat(model='gemma3', messages=[message], stream=True):
    print(part['message']['content'], end='', flush=True)

asyncio.run(chat())
## API

[](#api)
The Ollama Python library's API is designed around the [Ollama REST API](https://github.com/ollama/ollama/blob/main/docs/api.md)

### Chat

[](#chat)
ollama.chat(model='gemma3', messages=[{'role': 'user', 'content': 'Why is the sky blue?'}])
### Generate

[](#generate)
ollama.generate(model='gemma3', prompt='Why is the sky blue?')
### List

[](#list)
ollama.list()
### Show

[](#show)
ollama.show('gemma3')
### Create

[](#create)
ollama.create(model='example', from_='gemma3', system="You are Mario from Super Mario Bros.")
### Copy

[](#copy)
ollama.copy('gemma3', 'user/gemma3')
### Delete

[](#delete)
ollama.delete('gemma3')
### Pull

[](#pull)
ollama.pull('gemma3')
### Push

[](#push)
ollama.push('user/gemma3')
### Embed

[](#embed)
ollama.embed(model='gemma3', input='The sky is blue because of rayleigh scattering')
### Embed (batch)

[](#embed-batch)
ollama.embed(model='gemma3', input=['The sky is blue because of rayleigh scattering', 'Grass is green because of chlorophyll'])
### Ps

[](#ps)
ollama.ps()
## Errors

[](#errors)
Errors are raised if requests return an error status or if an error is detected while streaming.

model = 'does-not-yet-exist'

try:
  ollama.chat(model)
except ollama.ResponseError as e:
  print('Error:', e.error)
  if e.status_code == 404:
    ollama.pull(model)