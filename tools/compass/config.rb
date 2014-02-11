# Configuration file for compass
# see http://wiki.github.com/chriseppstein/compass/configuration-reference

project_type = :stand_alone
environment = :production  # :production or :development
                           # :development prints debugging comments in CSS
output_style = :compact    # :nested, :expanded, :compact, or :compressed
relative_assets = true

# file system paths
project_path = "../../"
sass_dir = "tools/compass/src"
# images_dir = "src/static/img"
images_dir = "tools/compass/images"
css_dir = "src/static/css"

# imports
# add_import_path "tools/compass/mixins"

# web server paths
#http_path = "/static"
http_images_path = "img"
http_stylesheets_path = "css"
http_javascripts_path = "js"


# cache busting
#  if the file exists, append the mtime (in secs).  else, append now (in secs).
asset_cache_buster do |http_path, real_path|
  if File.exists?(real_path)
    File.mtime(real_path).strftime("%s") 
  else
    DateTime.now.strftime("%s")
  end
end


