from ippai.simulate import Tags


def preprocess_image(settings, image_data):
    """
    Preprocess a photoacoustic image depending on the properties defined by the settings.

    :param settings: (dict) Dictionary that describes all simulation parameters.
    :param image_data: (numpy array) Image to be preprocessed.
    :return: Preprocessed image.
    """

    if Tags.CROP_IMAGE in settings:
        if settings[Tags.CROP_IMAGE]:
            if Tags.AIR_LAYER_HEIGHT_MM in settings:
                air_layer_height = int(settings[Tags.AIR_LAYER_HEIGHT_MM] / settings[Tags.SPACING_MM])
                image_data = image_data[air_layer_height:, :]

            if Tags.GELPAD_LAYER_HEIGHT_MM in settings:
                gelpad_layer_height = int(settings[Tags.GELPAD_LAYER_HEIGHT_MM] / settings[Tags.SPACING_MM])
                image_data = image_data[gelpad_layer_height:, :]

            if Tags.CROP_POWER_OF_TWO in settings:
                if settings[Tags.CROP_POWER_OF_TWO]:
                    print("Previous sizes: ", image_data.shape)
                    image_data = top_center_crop_power_two(image_data)
                    print("New sizes: ", image_data.shape)

    return image_data


def crop(image_data, height_start, width_start, target_height, target_width):
    """
    crop the given image.

    :param image_data: (numpy array) Image to be cropped.
    :param height_start: (int) height_start in (height_start,width_start) i.e coordinates of the upper left corner.
    :param width_start: (int) width_start in (height_start,width_start) i.e coordinates of the upper left corner.
    :param target_height: (int) Height of the cropped image.
    :param target_width: (int) Width of the cropped image.:
    :return: Cropped image.
    """

    return image_data[height_start:height_start + target_height, width_start:width_start + target_width]


def top_center_crop(image_data, output_size):
    """
    Center crop the given image.

    :param image_data: (numpy array) Image to be cropped.
    :param output_size: (int, list or tuple) Size as (height, width) of the cropped image.
                        If given as int, the output size will be quadratic.
    :return: Cropped image.
    """

    if isinstance(output_size, int):
        output_size = (output_size, output_size)
    elif not (isinstance(output_size, tuple) or isinstance(output_size, list)):
        raise TypeError("Output size has to be tuple or list.")

    target_height, target_width = output_size
    input_height, input_width = image_data.shape

    width_start = int((input_width - target_width)/2)

    return crop(image_data, 0, width_start, target_height, target_width)


def top_center_crop_power_two(image_data):
    """
    Center crop the given image to the sizes of the largest powers of two smaller
    than the image height and width, respectively.

    :param image_data: (numpy array) Image to be preprocessed.
    :param settings: (dict) Dictionary that describes all simulation parameters can be passed.
    :return: Cropped image.
    """

    input_height, input_width = image_data.shape
    target_height = 1 << (input_height.bit_length() - 1)
    target_width = 1 << (input_width.bit_length() - 1)

    return top_center_crop(image_data, (target_height, target_width))