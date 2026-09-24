from dify_plugin import DifyPluginEnv, Plugin

# Image and video generation are long jobs: a 4k image can take ten minutes and a video
# one to three. The default request timeout would abort work that has already been paid
# for, so it is raised here rather than inside each tool.
plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=660))

if __name__ == "__main__":
    plugin.run()
