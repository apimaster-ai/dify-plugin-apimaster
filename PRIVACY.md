# Privacy

This plugin is a client. It stores nothing and sends nothing anywhere except the endpoint
you configure.

## What is sent, and where

When you invoke a model or a tool, the plugin sends your prompt, any reference image URLs
you supply, and the parameters you chose to the **Base URL configured in the credential**
— by default `https://apimaster.ai/v1`. If you point the Base URL at a different
OpenAI-compatible gateway, that provider receives the data instead.

Generated images and videos are downloaded from that endpoint and handed to Dify as files,
so they are stored wherever your Dify instance stores workflow files.

## What is stored by the plugin

Nothing. There is no database, no cache and no log file of its own. Your API key lives in
Dify's credential store; the plugin reads it per request and never writes it anywhere.

## What is not collected

No telemetry, no analytics, no crash reporting, no usage statistics are sent to the plugin
author.

## Third parties

The endpoint you configure is the only third party involved. Its handling of your data is
governed by its own policy — for the default endpoint, see
<https://apimaster.ai/privacy>.

## Contact

Questions about this plugin: <https://github.com/apimaster-ai/dify-plugin-apimaster/issues>
