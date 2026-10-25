/*
 * Shows Previous's picture pixel-exact: the 1120 by 832 of the real hardware
 * scaled by the largest whole number the monitor allows, every pixel a sharp
 * block, instead of stretched to fit the screen and blurred.
 *
 * Previous presents full screen with SDL_LOGICAL_PRESENTATION_LETTERBOX and
 * SDL's default linear sampling. Loaded into Previous alone through
 * LD_PRELOAD, this library stands in front of the two SDL calls that decide
 * how the picture reaches the monitor, so neither Previous nor its package
 * changes:
 *
 *   SDL_SetRenderLogicalPresentation is passed on and remembered, so it is
 *   known which renderer Previous wants letterboxed and at what size.
 *
 *   SDL_RenderTexture checks, for that renderer, whether the output holds the
 *   whole picture at least once. Where it does, the presentation becomes
 *   SDL_LOGICAL_PRESENTATION_INTEGER_SCALE and the texture is sampled
 *   nearest. Where it does not, both stay what Previous asked for: SDL never
 *   scales an integer presentation below 1 (UpdateLogicalPresentation in
 *   src/render/SDL_render.c of release-3.2.10), so a monitor smaller than the
 *   picture would show only its middle.
 *
 * The check happens where the picture is drawn rather than where the mode is
 * set, because Previous sets the mode before its window has reached the size
 * of the screen it goes full screen on.
 *
 * PREVIOUSLY_PIXEL_EXACT_LOG names a file each change of presentation is
 * appended to.
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>

#include <SDL3/SDL.h>

#define LOG_VARIABLE "PREVIOUSLY_PIXEL_EXACT_LOG"

typedef bool (*PresentationSetter)(SDL_Renderer *renderer, int width, int height,
                                   SDL_RendererLogicalPresentation mode);
typedef bool (*TextureDrawer)(SDL_Renderer *renderer, SDL_Texture *texture,
                              const SDL_FRect *source, const SDL_FRect *destination);

/* The renderer Previous asked to letterbox and the size of its picture. One is
 * enough: Previous has one main window, and the NeXTdimension windows it opens
 * beside it ask for a stretched presentation, which is left alone. */
static SDL_Renderer *letterboxed_renderer = NULL;
static int picture_width = 0;
static int picture_height = 0;

/* Whether that renderer is presenting by whole numbers right now. */
static bool presenting_exact = false;

/* Appends one line to the file PREVIOUSLY_PIXEL_EXACT_LOG names, if it names one. */
static void note(const char *format, ...)
{
    const char *path = getenv(LOG_VARIABLE);
    FILE *log;
    va_list arguments;

    if (path == NULL || *path == '\0') {
        return;
    }
    log = fopen(path, "a");
    if (log == NULL) {
        return;
    }
    va_start(arguments, format);
    vfprintf(log, format, arguments);
    va_end(arguments);
    fputc('\n', log);
    fclose(log);
}

/* SDL's own definition of a function this library stands in front of. */
static void *sdl_definition(const char *name)
{
    void *definition = dlsym(RTLD_NEXT, name);
    if (definition == NULL) {
        note("%s not found after this library: %s", name, dlerror());
    }
    return definition;
}

static PresentationSetter sdl_set_presentation(void)
{
    static PresentationSetter setter = NULL;
    if (setter == NULL) {
        setter = (PresentationSetter)sdl_definition("SDL_SetRenderLogicalPresentation");
    }
    return setter;
}

static TextureDrawer sdl_render_texture(void)
{
    static TextureDrawer drawer = NULL;
    if (drawer == NULL) {
        drawer = (TextureDrawer)sdl_definition("SDL_RenderTexture");
    }
    return drawer;
}

/* Presents by whole numbers where the output holds the whole picture at least
 * once, and letterboxed as Previous asked where it does not. Changes the
 * presentation only when the answer changes, which is when the window has
 * reached its full-screen size or the monitor has changed. */
static void fit_presentation(SDL_Renderer *renderer)
{
    int output_width = 0;
    int output_height = 0;
    bool holds_picture;
    SDL_RendererLogicalPresentation mode;

    if (!SDL_GetRenderOutputSize(renderer, &output_width, &output_height)) {
        return;
    }
    holds_picture = output_width >= picture_width && output_height >= picture_height;
    if (holds_picture == presenting_exact) {
        return;
    }
    mode = holds_picture ? SDL_LOGICAL_PRESENTATION_INTEGER_SCALE : SDL_LOGICAL_PRESENTATION_LETTERBOX;
    if (sdl_set_presentation()(renderer, picture_width, picture_height, mode)) {
        presenting_exact = holds_picture;
        note("output %d by %d, picture %d by %d: %s", output_width, output_height,
             picture_width, picture_height, holds_picture ? "whole numbers, nearest" : "letterbox, linear");
    }
}

bool SDL_SetRenderLogicalPresentation(SDL_Renderer *renderer, int width, int height,
                                      SDL_RendererLogicalPresentation mode)
{
    PresentationSetter setter = sdl_set_presentation();

    if (setter == NULL) {
        return false;
    }
    if (mode == SDL_LOGICAL_PRESENTATION_LETTERBOX) {
        letterboxed_renderer = renderer;
        picture_width = width;
        picture_height = height;
    } else if (renderer == letterboxed_renderer) {
        letterboxed_renderer = NULL;
    }
    presenting_exact = false;
    return setter(renderer, width, height, mode);
}

bool SDL_RenderTexture(SDL_Renderer *renderer, SDL_Texture *texture,
                       const SDL_FRect *source, const SDL_FRect *destination)
{
    TextureDrawer drawer = sdl_render_texture();
    SDL_ScaleMode wanted;
    SDL_ScaleMode current;

    if (drawer == NULL) {
        return false;
    }
    if (renderer == letterboxed_renderer) {
        fit_presentation(renderer);
        wanted = presenting_exact ? SDL_SCALEMODE_NEAREST : SDL_SCALEMODE_LINEAR;
        if (SDL_GetTextureScaleMode(texture, &current) && current != wanted) {
            SDL_SetTextureScaleMode(texture, wanted);
        }
    }
    return drawer(renderer, texture, source, destination);
}
