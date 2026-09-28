from dify_plugin import DifyPluginEnv, Plugin

# Image and video generation are long jobs: a 4k image can take ten minutes. The default
# request timeout would abort work that has already been paid for, so it is raised here.
# Video is slower still (~15 minutes), longer than Dify lets a call run, so the video tool
# returns a task id after ~8.5 minutes and the Get Video tool fetches it later.
plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=660))

if __name__ == "__main__":
    plugin.run()
