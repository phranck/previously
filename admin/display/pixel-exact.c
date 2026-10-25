/*
 * Shows Previous's picture sharp at any size: the 1120 by 832 of the real
 * hardware fills the monitor as before, but with edges at most one pixel soft
 * instead of blurred all over.
 *
 * Previous presents full screen with SDL_LOGICAL_PRESENTATION_LETTERBOX and
 * SDL's default linear sampling, so its picture is stretched to fit the
 * monitor by whatever factor that takes, 1.83 on a 2048 by 1536 display, and
 * every pixel is smeared into its neighbours. Scaling by whole numbers alone
 * keeps it sharp but leaves it small wherever the monitor is less than twice
 * the picture. So the picture is scaled in two steps, which emulators call
 * sharp bilinear: first with nearest sampling to the next whole multiple of
 * its size, then with linear sampling down to the size the letterbox gives
 * it. Where the factor is a whole number the second step changes nothing, and
 * where the monitor is smaller than the picture the first step is left out.
 * SDL 3.4 does the same as SDL_SCALEMODE_PIXELART; the Pi runs SDL 3.2.10.
 *
 * Loaded into Previous alone through LD_PRELOAD, the library stands in front
 * of two SDL calls, so neither Previous nor its package changes:
 *
 *   SDL_SetRenderLogicalPresentation is passed on unchanged and remembered,
 *   so it is known which renderer Previous letterboxes and at what size.
 *
 *   SDL_RenderTexture draws that renderer's opaque textures, which is the
 *   emulated screen, through the enlarged copy. Previous's own interface is
 *   drawn blended over it and is passed on unchanged.
 *
 * PREVIOUSLY_PIXEL_EXACT_LOG names a file that every presentation Previous
 * asks for, and every change of the enlarging factor, is appended to.
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>

#include <SDL3/SDL.h>

#define LOG_VARIABLE "PREVIOUSLY_PIXEL_EXACT_LOG"

/* Keeps a factor that is a whole number but comes out a hair below it in
 * floating point from being rounded up to the next one. */
#define WHOLE_NUMBER_TOLERANCE 0.0001f

typedef bool (*PresentationSetter)(SDL_Renderer *renderer, int width, int height,
                                   SDL_RendererLogicalPresentation mode);
typedef bool (*TextureDrawer)(SDL_Renderer *renderer, SDL_Texture *texture,
                              const SDL_FRect *source, const SDL_FRect *destination);

/* The renderer Previous letterboxes and the size of its picture. One is
 * enough: Previous has one main window, and the NeXTdimension windows it opens
 * beside it ask for a stretched presentation, which is left alone. */
static SDL_Renderer *letterboxed_renderer = NULL;
static int picture_width = 0;
static int picture_height = 0;

/* The enlarged copy of the picture, kept from frame to frame, and the factor
 * it was made for. */
static SDL_Texture *enlarged = NULL;
static int enlarged_factor = 0;

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

/* The whole number the picture is enlarged by before it is scaled to the
 * monitor: the letterbox factor rounded up, and no larger than the renderer's
 * biggest texture allows. 1 means the picture is drawn as Previous draws it. */
static int enlarging_factor(SDL_Renderer *renderer, SDL_Texture *texture)
{
    int output_width = 0;
    int output_height = 0;
    float across;
    float down;
    int factor;
    Sint64 largest;

    if (picture_width <= 0 || picture_height <= 0 ||
        !SDL_GetRenderOutputSize(renderer, &output_width, &output_height)) {
        return 1;
    }
    across = (float)output_width / (float)picture_width;
    down = (float)output_height / (float)picture_height;
    factor = (int)SDL_ceilf((across < down ? across : down) - WHOLE_NUMBER_TOLERANCE);

    largest = SDL_GetNumberProperty(SDL_GetRendererProperties(renderer),
                                    SDL_PROP_RENDERER_MAX_TEXTURE_SIZE_NUMBER, 0);
    while (largest > 0 && factor > 1 &&
           ((Sint64)factor * texture->w > largest || (Sint64)factor * texture->h > largest)) {
        factor--;
    }
    return factor < 1 ? 1 : factor;
}

/* The enlarged copy for this factor, made anew when the factor or the
 * picture's size changes, or NULL where the renderer cannot make one. */
static SDL_Texture *enlarged_copy(SDL_Renderer *renderer, SDL_Texture *texture, int factor)
{
    int width = factor * texture->w;
    int height = factor * texture->h;

    if (enlarged != NULL && enlarged_factor == factor &&
        enlarged->w == width && enlarged->h == height) {
        return enlarged;
    }
    if (enlarged != NULL) {
        SDL_DestroyTexture(enlarged);
        enlarged = NULL;
    }
    enlarged = SDL_CreateTexture(renderer, texture->format, SDL_TEXTUREACCESS_TARGET, width, height);
    if (enlarged == NULL) {
        note("no enlarged copy of %d by %d: %s", width, height, SDL_GetError());
        enlarged_factor = 0;
        return NULL;
    }
    SDL_SetTextureBlendMode(enlarged, SDL_BLENDMODE_NONE);
    SDL_SetTextureScaleMode(enlarged, SDL_SCALEMODE_LINEAR);
    enlarged_factor = factor;
    note("picture %d by %d enlarged %d times to %d by %d, then scaled to fit",
         texture->w, texture->h, factor, width, height);
    return enlarged;
}

/* Whether the texture is drawn without blending, which in Previous's
 * letterboxed window is the emulated screen. */
static bool is_opaque(SDL_Texture *texture)
{
    SDL_BlendMode mode;
    return SDL_GetTextureBlendMode(texture, &mode) && mode == SDL_BLENDMODE_NONE;
}

bool SDL_SetRenderLogicalPresentation(SDL_Renderer *renderer, int width, int height,
                                      SDL_RendererLogicalPresentation mode)
{
    PresentationSetter setter = sdl_set_presentation();

    if (setter == NULL) {
        return false;
    }
    note("Previous asks for presentation %d at %d by %d", (int)mode, width, height);
    if (mode == SDL_LOGICAL_PRESENTATION_LETTERBOX) {
        letterboxed_renderer = renderer;
        picture_width = width;
        picture_height = height;
    } else if (renderer == letterboxed_renderer) {
        letterboxed_renderer = NULL;
    }
    return setter(renderer, width, height, mode);
}

bool SDL_RenderTexture(SDL_Renderer *renderer, SDL_Texture *texture,
                       const SDL_FRect *source, const SDL_FRect *destination)
{
    TextureDrawer drawer = sdl_render_texture();
    SDL_Texture *copy;
    SDL_Texture *target;
    SDL_ScaleMode sampling;
    int factor;

    if (drawer == NULL) {
        return false;
    }
    if (renderer != letterboxed_renderer || !is_opaque(texture)) {
        return drawer(renderer, texture, source, destination);
    }
    factor = enlarging_factor(renderer, texture);
    copy = factor > 1 ? enlarged_copy(renderer, texture, factor) : NULL;
    if (copy == NULL) {
        return drawer(renderer, texture, source, destination);
    }

    /* Into the copy with nearest sampling, so every pixel becomes a block of
     * factor by factor, then the copy onto the screen with linear sampling. */
    target = SDL_GetRenderTarget(renderer);
    if (!SDL_GetTextureScaleMode(texture, &sampling)) {
        sampling = SDL_SCALEMODE_LINEAR;
    }
    SDL_SetTextureScaleMode(texture, SDL_SCALEMODE_NEAREST);
    SDL_SetRenderTarget(renderer, copy);
    drawer(renderer, texture, source, NULL);
    SDL_SetRenderTarget(renderer, target);
    SDL_SetTextureScaleMode(texture, sampling);
    return drawer(renderer, copy, NULL, destination);
}
