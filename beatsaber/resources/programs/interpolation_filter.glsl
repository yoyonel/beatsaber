#version 330

#if defined VERTEX_SHADER
in vec3 in_position;
in vec2 in_texcoord_0;
out vec2 uv;

void main() {
    gl_Position = vec4(in_position, 1.0);
    uv = in_texcoord_0;
}

    #elif defined FRAGMENT_SHADER

out vec4 outColor;
in vec2 uv;
uniform sampler2D texture0;

const int NUM_LAYERS = 10;
const float gamma = 2.2;


vec4 filter_fetch(sampler2D tex, vec2 uv, int layer) {
    ivec2 textureResolution = textureSize(texture0, layer);
    uv = uv*textureResolution + 0.5;
    vec2 iuv = floor(uv);
    vec2 fuv = fract(uv);
    uv = iuv + fuv * fuv * (3.0 - 2.0 * fuv);
    uv = (uv - 0.5)/textureResolution;
    // https://www.khronos.org/registry/OpenGL-Refpages/gl4/html/textureLod.xhtml
    return textureLod(tex, uv, layer);
}

// from http://www.java-gaming.org/index.php?topic=35123.0
vec4 cubic(float v){
    vec4 n = vec4(1.0, 2.0, 3.0, 4.0) - v;
    vec4 s = n * n * n;
    float x = s.x;
    float y = s.y - 4.0 * s.x;
    float z = s.z - 4.0 * s.y + 6.0 * s.x;
    float w = 6.0 - x - y - z;
    return vec4(x, y, z, w) * (1.0/6.0);
}

vec4 textureBicubic(sampler2D sampler, vec2 texCoords, int layer){

    vec2 texSize = textureSize(sampler, layer);
    vec2 invTexSize = 1.0 / texSize;

    texCoords = texCoords * texSize - 0.5;


    vec2 fxy = fract(texCoords);
    texCoords -= fxy;

    vec4 xcubic = cubic(fxy.x);
    vec4 ycubic = cubic(fxy.y);

    vec4 c = texCoords.xxyy + vec2 (-0.5, +1.5).xyxy;

    vec4 s = vec4(xcubic.xz + xcubic.yw, ycubic.xz + ycubic.yw);
    vec4 offset = c + vec4 (xcubic.yw, ycubic.yw) / s;

    offset *= invTexSize.xxyy;

    vec4 sample0 = textureLod(sampler, offset.xz, layer);
    vec4 sample1 = textureLod(sampler, offset.yz, layer);
    vec4 sample2 = textureLod(sampler, offset.xw, layer);
    vec4 sample3 = textureLod(sampler, offset.yw, layer);

    float sx = s.x / (s.x + s.y);
    float sy = s.z / (s.z + s.w);

    return mix(mix(sample3, sample2, sx), mix(sample1, sample0, sx), sy);
}


// https://www.shadertoy.com/view/lslGzl
vec3 Uncharted2ToneMapping(vec3 color)
{
    float A = 0.15;
    float B = 0.50;
    float C = 0.10;
    float D = 0.20;
    float E = 0.02;
    float F = 0.30;
    float W = 11.2;
    float exposure = 2.;
    color *= exposure;
    color = ((color * (A * color + C * B) + D * E) / (color * (A * color + B) + D * F)) - E / F;
    float white = ((W * (A * W + C * B) + D * E) / (W * (A * W + B) + D * F)) - E / F;
    color /= white;
    color = pow(color, vec3(1. / gamma));
    return color;
}

void main() {
    vec4 col = vec4(0.0);
    for (int layer = 3; layer < NUM_LAYERS; layer++) {
        col += textureBicubic(texture0, uv, layer);
        //                col += filter_fetch(texture0, uv, layer);
        //                col += textureLod(texture0, uv, layer);
    }

    vec3 hdrColor = Uncharted2ToneMapping(col.rgb);

    outColor = vec4(hdrColor, 1.0);
}

    #endif
