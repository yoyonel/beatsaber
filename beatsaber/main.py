from pathlib import Path
import moderngl
import moderngl_window
from pyglet.media import Player, StaticSource, load
from moderngl_window.scene import KeyboardCamera
from moderngl_window import geometry
from track import BSTrack
from scene import BSScene

RESOURCE_DIR = Path(__file__).parent.resolve() / 'resources'


class BeatSaber(moderngl_window.WindowConfig):
    title = "Beat Saber Light Show"
    window_size = 1920, 1080
    # window_size = 1920 >> 1, 1080 >> 1
    cursor = False
    aspect_ratio = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.wnd.mouse_exclusivity = False
        self.bpm = 242  # Hardcode bpm from info.dat
        self.camera = KeyboardCamera(self.wnd.keys, fov=60, near=1.0, far=1000.0)
        self.camera.velocity = 50
        self.camera_enabled = False

        meta = self.load_json('megalovania_remix/info.dat')
        self.map = BSScene(
            self.load_scene('bs_map3.glb'),
            self.camera,
            BSTrack('megalovania_remix/Expert.dat', meta['_beatsPerMinute']),
        )

        self.quad_fs = geometry.quad_fs()

        # Postprocess programs
        self.copy_prog = self.load_program('programs/copy.glsl')
        self.blur_h_prog = self.load_program('programs/blur_h.glsl')
        self.blur_v_prog = self.load_program('programs/blur_v.glsl')
        self.combine = self.load_program('programs/combine.glsl')
        self.combine['texture1'] = 1
        self.interpolation_filter_prog = self.load_program('programs/interpolation_filter.glsl')

        # blur stuff
        self.offscreen_texture = self.ctx.texture((self.wnd.buffer_width, self.wnd.buffer_height), 4)
        self.offscreen_texture.repeat_x = False
        self.offscreen_texture.repeat_y = False
        self.offscreen_depth = self.ctx.depth_texture((self.wnd.buffer_width, self.wnd.buffer_height))
        self.offscreen = self.ctx.framebuffer(
            color_attachments=[self.offscreen_texture],
            depth_attachment=self.offscreen_depth,
        )
        bd = 1
        self.blur_h_texture = self.ctx.texture((self.wnd.buffer_width // bd, self.wnd.buffer_height // bd), 4)
        self.blur_h_texture.repeat_x = False
        self.blur_h_texture.repeat_y = False
        self.blur_h = self.ctx.framebuffer(color_attachments=[self.blur_h_texture])
        self.blur_v_texture = self.ctx.texture((self.wnd.buffer_width // bd, self.wnd.buffer_height // bd), 4)
        self.blur_v_texture.repeat_x = False
        self.blur_v_texture.repeat_y = False
        self.blur_v = self.ctx.framebuffer(color_attachments=[self.blur_v_texture])
        #
        self.interpolation_filter_texture = self.ctx.texture((self.wnd.buffer_width // bd, self.wnd.buffer_height // bd), 4)
        self.interpolation_filter_texture.repeat_x = False
        self.interpolation_filter_texture.repeat_y = False
        self.interpolation_filter = self.ctx.framebuffer(color_attachments=[self.interpolation_filter_texture])

        self.music_player = Player()
        self.music_source = StaticSource(load(RESOURCE_DIR / 'megalovania_remix/song.wav'))
        self.music_player.queue(self.music_source)
        self.music_player.play()
        self.music_player.seek(60.0 * 4 + 50)
        self.music_player.volume = 1.0

        self.query = self.ctx.query(time=True)
        self.acc_timestamp = 0
        self.nb_query = 0

    def _render_with_blur(self):
        self.blur_h.clear()
        self.blur_v.clear()

        self.blur_v.use()
        self.offscreen_texture.use(location=0)
        self.quad_fs.render(self.copy_prog)
        self.blur_v_texture.build_mipmaps(max_level=10)

        self.blur_h.use()
        self.blur_v_texture.use(location=0)
        self.quad_fs.render(self.blur_h_prog)
        self.blur_h_texture.build_mipmaps(max_level=10)

        self.blur_v.use()
        self.blur_h_texture.use(location=0)
        self.quad_fs.render(self.blur_v_prog)

        return self.blur_v_texture

    def _render_with_interpolation_filter(self):
        self.interpolation_filter.clear()
        self.offscreen_texture.build_mipmaps(max_level=10)
        self.interpolation_filter.use()
        self.offscreen_texture.use(location=0)
        self.quad_fs.render(self.interpolation_filter_prog)
        return self.interpolation_filter_texture

    def render(self, time, frame_time):
        with self.query:
            self.offscreen.clear()
            time = self.music_player.time

            self.offscreen.use()
            self.ctx.enable_only(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
            self.map.render(self.camera, time, frame_time)

            self.ctx.enable_only(moderngl.NOTHING)

            # filter_result_texture = self._render_with_blur()
            filter_result_texture = self._render_with_interpolation_filter()

            # Back to screen
            self.wnd.fbo.use()
            self.offscreen_texture.use(location=0)
            filter_result_texture.use(location=1)
            self.quad_fs.render(self.combine)

        self.nb_query += 1
        self.acc_timestamp += self.query.elapsed / 1e6
        if not (self.nb_query % 60):
            print("GPU - ::render() -> {:.4f} ms".format(self.acc_timestamp / self.nb_query))
            self.nb_query = 0
            self.acc_timestamp = 0

    def key_event(self, key, action, modifiers):
        keys = self.wnd.keys

        if self.camera_enabled:
            self.camera.key_input(key, action, modifiers)

        if action == keys.ACTION_PRESS:
            if key == keys.C:
                self.camera_enabled = not self.camera_enabled
                self.wnd.mouse_exclusivity = self.camera_enabled
                self.wnd.cursor = not self.camera_enabled
            if key == keys.SPACE:
                self.timer.toggle_pause()
                if self.music_player.playing:
                    self.music_player.pause()
                else:
                    self.music_player.play()

    def mouse_position_event(self, x: int, y: int, dx, dy):
        if self.camera_enabled:
            self.camera.rot_state(-dx, -dy)

    def resize(self, width: int, height: int):
        self.camera.projection.update(aspect_ratio=self.wnd.aspect_ratio)
        self.map.resize()


if __name__ == '__main__':
    moderngl_window.run_window_config(BeatSaber)
