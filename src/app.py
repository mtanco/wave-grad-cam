import os
import toml

from h2o_wave import Q, ui, app, main, on, handle_on

from .image_utils import get_superimposed_image


@app('/')
async def serve(q: Q):

    if not q.client.initialized:
        await initialize_client(q)

    await handle_on(q)
    await q.page.save()


async def initialize_client(q: Q):

    if not q.app.initialized:
        q.app.toml = toml.load("app.toml")
        q.app.initialized = True

    q.client.images = {}
    for image_name in os.listdir('./images'):
        q.client.images[image_name] = os.path.join("./images", image_name)

    q.page['meta'] = ui.meta_card(
        box='',
        title='Wave Grad-CAM',
        layouts=[
            # xs: portrait phones, s: landscape phones, m: tablets, l: desktop, xl: large desktop
            ui.layout(breakpoint='xs', zones=[ui.zone("device-not-supported")]),
            ui.layout(
                breakpoint='m',
                max_width="1200px",
                height="vh100",
                zones=[ui.zone('header'), ui.zone('content', size="1"), ui.zone('footer')]
            )
        ]
    )

    q.page['device-not-supported'] = ui.form_card(
        box='device-not-supported',
        items=[
            ui.text_xl("This app was built for tablets or desktop and is not available on mobile.")
        ]
    )

    q.page['header'] = ui.header_card(
        box='header',
        title=f"{q.app.toml['App']['Title']} v{q.app.toml['App']['Version']}",
        subtitle=q.app.toml['App']['Description'],
        image='https://cloud.h2o.ai/logo.svg',
        items=[
            ui.dropdown(name='image_selected',
                        label='Select an Image: ',
                        width='200px',
                        choices=[ui.choice(name=k, label=k) for k in q.client.images.keys()],
                        trigger=True),
            ui.button(name='upload_side_panel', label="Upload New Image", primary=True)
        ]

    )
    q.page['content'] = ui.form_card(box="content", items=[])
    q.page['footer'] = ui.footer_card(
        box='footer',
        caption='Made with 💛 using <a href="https://wave.h2o.ai" target="_blank">H2O Wave</a> and '
                '<a href="https://keras.io/examples/vision/grad_cam/" target="_blank">Keras Grad-CAM</a>'
    )
    await q.page.save()
    q.page['content'].items = await image_gradcam(q, list(q.client.images.keys())[0])

    q.client.initialized = True


@on()
async def image_selected(q: Q):

    q.page['content'].items = await image_gradcam(q, q.args.image_selected)


@on()
async def upload_side_panel(q: Q):
    q.page["meta"].side_panel = ui.side_panel(
        title="Add your own image",
        closable=True,
        blocking=False,
        items=[
            ui.file_upload(
                name='image_uploaded',
                label='Upload Image',
                multiple=False,
                file_extensions=['png', 'jpg', 'jpeg']
            )
        ]
    )


@on()
async def image_uploaded(q: Q):

    q.page["meta"].side_panel = None

    local_file_path = await q.site.download(url=q.args.image_uploaded[0], path='./images')
    image_name = os.path.basename(local_file_path)

    q.client.images[image_name] = local_file_path
    q.page["header"].items[0].dropdown.choices = [ui.choice(name=k, label=k) for k in q.client.images.keys()]

    q.page['content'].items = await image_gradcam(q, image_name)


async def image_gradcam(q, image_name):
    await making_prediction(q)

    q.page["header"].items[0].dropdown.value = image_name

    model_prediction, gradcam_image_path = get_superimposed_image(q.client.images[image_name])
    gradcam_wave_image_path, = await q.site.upload([gradcam_image_path])
    os.remove(gradcam_image_path)

    items = [
        ui.text_xl(f'<center><b>Prediction:</b> {model_prediction[1]}</center>'),
        ui.text_l('<center><b>Confidence:</b> {:.2%}</center>'.format(model_prediction[2])),

        ui.frame(content=' ', height="20px"),

        ui.markup(f'<center><img style="max-width: 50%; max-height: 50%;" src="{gradcam_wave_image_path}"/></center>'),
    ]
    return items


async def making_prediction(q: Q):
    q.page["meta"].dialog = ui.dialog(
        title="Making Image Prediction",
        blocking=True,
        closable=False,
        items=[
            ui.progress('Analyzing your image with Keras')
        ]
    )
    await q.page.save()
    q.page["meta"].dialog = None
